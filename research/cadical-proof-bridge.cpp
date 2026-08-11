// Minimal C ABI for an in-process, proof-tracing CaDiCaL shadow solver.

#include "cadical.hpp"

#include <chrono>
#include <climits>
#include <cstddef>
#include <cstdio>
#include <exception>
#include <new>

namespace {

void set_error(char *buffer, std::size_t size, const char *message) {
  if (!buffer || !size) return;
  std::snprintf(buffer, size, "%s", message ? message : "unknown error");
}

class DeadlineTerminator : public CaDiCaL::Terminator {
 public:
  explicit DeadlineTerminator(double seconds)
      : deadline_(std::chrono::steady_clock::now() +
                  std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                      std::chrono::duration<double>(seconds))) {}

  bool terminate() override {
    return std::chrono::steady_clock::now() >= deadline_;
  }

 private:
  std::chrono::steady_clock::time_point deadline_;
};

struct ShadowSolver {
  CaDiCaL::Solver solver;
  bool proof_closed = false;
  bool solved = false;
};

}  // namespace

extern "C" {

const char *no3_cadical_version() { return CaDiCaL::Solver::version(); }

void *no3_cadical_create(const char *proof_path, int factor, char *error,
                         std::size_t error_size) {
  if (!proof_path || !*proof_path) {
    set_error(error, error_size, "proof path is empty");
    return nullptr;
  }
  try {
    auto *shadow = new ShadowSolver;
    shadow->solver.set("quiet", 1);
    shadow->solver.set("binary", 1);
    if (!shadow->solver.set("factor", factor ? 1 : 0)) {
      set_error(error, error_size, "CaDiCaL does not support the factor option");
      delete shadow;
      return nullptr;
    }
    if (!shadow->solver.trace_proof(proof_path)) {
      set_error(error, error_size, "could not open the CaDiCaL proof trace");
      delete shadow;
      return nullptr;
    }
    return shadow;
  } catch (const std::exception &exception) {
    set_error(error, error_size, exception.what());
  } catch (...) {
    set_error(error, error_size, "unknown exception while creating CaDiCaL");
  }
  return nullptr;
}

int no3_cadical_add(void *opaque, const int *literals, std::size_t length,
                    char *error, std::size_t error_size) {
  auto *shadow = static_cast<ShadowSolver *>(opaque);
  if (!shadow) {
    set_error(error, error_size, "CaDiCaL shadow is null");
    return -1;
  }
  if (shadow->solved) {
    set_error(error, error_size, "clauses cannot be added after shadow solve");
    return -1;
  }
  if (length && !literals) {
    set_error(error, error_size, "literal buffer is null");
    return -1;
  }
  if (length && literals[length - 1] != 0) {
    set_error(error, error_size, "literal buffer does not end with zero");
    return -1;
  }
  try {
    int maximum_variable = shadow->solver.vars();
    for (std::size_t index = 0; index < length; ++index) {
      if (literals[index] == INT_MIN) {
        set_error(error, error_size, "INT_MIN is not a valid literal");
        return -1;
      }
      const int variable = literals[index] < 0 ? -literals[index] : literals[index];
      if (variable > maximum_variable) maximum_variable = variable;
    }
    const int undeclared = maximum_variable - shadow->solver.vars();
    if (undeclared > 0) shadow->solver.declare_more_variables(undeclared);
    for (std::size_t index = 0; index < length; ++index) {
      shadow->solver.add(literals[index]);
    }
    return 0;
  } catch (const std::exception &exception) {
    set_error(error, error_size, exception.what());
  } catch (...) {
    set_error(error, error_size, "unknown exception while adding clauses");
  }
  return -1;
}

int no3_cadical_solve(void *opaque, double seconds, char *error,
                      std::size_t error_size) {
  auto *shadow = static_cast<ShadowSolver *>(opaque);
  if (!shadow) {
    set_error(error, error_size, "CaDiCaL shadow is null");
    return -1;
  }
  if (shadow->solved) {
    set_error(error, error_size, "CaDiCaL shadow can only be solved once");
    return -1;
  }
  if (!(seconds > 0.0)) {
    set_error(error, error_size, "solve timeout must be positive");
    return -1;
  }
  try {
    DeadlineTerminator terminator(seconds);
    shadow->solver.connect_terminator(&terminator);
    int status;
    try {
      status = shadow->solver.solve();
    } catch (...) {
      shadow->solver.disconnect_terminator();
      throw;
    }
    shadow->solver.disconnect_terminator();
    shadow->solver.close_proof_trace();
    shadow->proof_closed = true;
    shadow->solved = true;
    return status;
  } catch (const std::exception &exception) {
    set_error(error, error_size, exception.what());
  } catch (...) {
    set_error(error, error_size, "unknown exception while solving");
  }
  return -1;
}

void no3_cadical_release(void *opaque) {
  auto *shadow = static_cast<ShadowSolver *>(opaque);
  if (!shadow) return;
  if (!shadow->proof_closed) shadow->solver.close_proof_trace();
  delete shadow;
}

}  // extern "C"
