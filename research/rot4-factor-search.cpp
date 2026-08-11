#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <mutex>
#include <numeric>
#include <random>
#include <regex>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using Clock = std::chrono::steady_clock;

namespace {

constexpr const char* kAlphabet =
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&@?!()[]<>{}=*+|-/~^_:;,.";

struct LineKey {
  int a;
  int b;
  int c;

  bool operator==(const LineKey& other) const {
    return a == other.a && b == other.b && c == other.c;
  }
};

struct LineHash {
  size_t operator()(const LineKey& line) const {
    uint64_t value = uint32_t(line.a + 127);
    value = value * 257 + uint32_t(line.b + 127);
    value = value * 32771 + uint32_t(line.c + 16384);
    value ^= value >> 29;
    value *= 0x9e3779b97f4a7c15ULL;
    return size_t(value ^ (value >> 32));
  }
};

struct ProgressEvent {
  long long milliseconds;
  long long energy;
  int thread;
};

struct SharedBest {
  explicit SharedBest(Clock::time_point started) : start(started) {}

  Clock::time_point start;
  std::mutex mutex;
  long long energy = std::numeric_limits<long long>::max();
  std::vector<int> edges;
  std::vector<ProgressEvent> progress;

  bool publish(long long next_energy, const std::vector<int>& next_edges, int thread) {
    std::lock_guard<std::mutex> lock(mutex);
    if (next_energy >= energy) return false;
    energy = next_energy;
    edges = next_edges;
    progress.push_back({
        std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - start).count(),
        energy,
        thread,
    });
    return true;
  }

  std::pair<long long, std::vector<int>> snapshot() {
    std::lock_guard<std::mutex> lock(mutex);
    return {energy, edges};
  }
};

struct Search {
  int n;
  int m;
  std::mt19937_64 rng;
  std::vector<std::array<int, 4>> orbit_points;
  std::vector<uint8_t> selected_cell;
  std::vector<uint8_t> selected_orbit;
  std::vector<int> points;
  std::vector<int> point_position;
  std::vector<int> edges;
  std::vector<long long> conflict_weights;
  std::unordered_map<LineKey, int, LineHash> line_counts;
  std::unordered_map<LineKey, int, LineHash> line_weights;
  std::vector<std::vector<int>> lift_pool;
  size_t lift_cursor = 0;
  long long energy = 0;
  long long weighted_energy = 0;
  long long initial_energy = 0;
  long long best_energy = 0;
  std::vector<int> best_edges;
  int four_edge_percent = 0;
  std::array<long long, 5> attempted_moves{};
  std::array<long long, 5> accepted_moves{};

  Search(int board_size, uint64_t seed)
      : n(board_size), m(board_size / 2), rng(seed) {
    orbit_points.resize(m * m);
    for (int row = 0; row < m; ++row) {
      for (int column = 0; column < m; ++column) {
        orbit_points[row * m + column] = {
            row * n + column,
            column * n + (n - 1 - row),
            (n - 1 - row) * n + (n - 1 - column),
            (n - 1 - column) * n + row,
        };
      }
    }

    selected_cell.assign(n * n, 0);
    selected_orbit.assign(m * m, 0);
    point_position.assign(n * n, -1);
  }

  LineKey canonical_line(int first, int second) const {
    const int first_row = first / n;
    const int first_column = first % n;
    const int second_row = second / n;
    const int second_column = second % n;
    int a = second_row - first_row;
    int b = first_column - second_column;
    int c = -(a * first_column + b * first_row);
    const int divisor = std::gcd(std::gcd(std::abs(a), std::abs(b)), std::abs(c));
    a /= divisor;
    b /= divisor;
    c /= divisor;
    if (a < 0 || (a == 0 && b < 0)) {
      a = -a;
      b = -b;
      c = -c;
    }
    return {a, b, c};
  }

  static long long choose_two(long long count) { return count * (count - 1) / 2; }

  static long long choose_three(long long count) {
    return count * (count - 1) * (count - 2) / 6;
  }

  int line_weight(const LineKey& line) const {
    const auto found = line_weights.find(line);
    return found == line_weights.end() ? 1 : found->second;
  }

  std::unordered_map<LineKey, int, LineHash> lines_through_point(int point) const {
    std::unordered_map<LineKey, int, LineHash> groups;
    groups.reserve(points.size() * 2 + 1);
    for (int other : points) ++groups[canonical_line(point, other)];
    return groups;
  }

  void add_point(int point) {
    const auto groups = lines_through_point(point);
    for (const auto& [line, count] : groups) {
      const long long delta = choose_two(count);
      energy += delta;
      weighted_energy += line_weight(line) * delta;
      line_counts[line] = count + 1;
    }
    selected_cell[point] = 1;
    point_position[point] = int(points.size());
    points.push_back(point);
  }

  void remove_point(int point) {
    const int position = point_position[point];
    const int last = points.back();
    points[position] = last;
    point_position[last] = position;
    points.pop_back();
    point_position[point] = -1;
    selected_cell[point] = 0;
    const auto groups = lines_through_point(point);
    for (const auto& [line, count] : groups) {
      const long long delta = choose_two(count);
      energy -= delta;
      weighted_energy -= line_weight(line) * delta;
      if (count == 1) {
        line_counts.erase(line);
      } else {
        line_counts[line] = count;
      }
    }
  }

  void add_orbit(int id) {
    for (int point : orbit_points[id]) add_point(point);
    selected_orbit[id] = 1;
  }

  void remove_orbit(int id) {
    for (int point : orbit_points[id]) remove_point(point);
    selected_orbit[id] = 0;
  }

  void set_edges(const std::vector<int>& next_edges) {
    if (next_edges.size() != size_t(m)) throw std::runtime_error("a factor must contain exactly m arcs");
    std::fill(selected_cell.begin(), selected_cell.end(), 0);
    std::fill(selected_orbit.begin(), selected_orbit.end(), 0);
    std::fill(point_position.begin(), point_position.end(), -1);
    points.clear();
    line_counts.clear();
    edges = next_edges;
    energy = 0;
    weighted_energy = 0;
    for (int id : edges) {
      if (id < 0 || id >= m * m || selected_orbit[id]) {
        throw std::runtime_error("factor contains an invalid or duplicate directed arc");
      }
      add_orbit(id);
    }
    initial_energy = energy;
    if (best_edges.empty() || energy < best_energy) {
      best_energy = energy;
      best_edges = edges;
    }
    conflict_weights.assign(m, 1);
  }

  void initialize_hamiltonian() {
    std::vector<int> order(m);
    std::iota(order.begin(), order.end(), 0);
    std::shuffle(order.begin(), order.end(), rng);

    std::vector<int> next_edges;
    next_edges.reserve(m);
    for (int index = 0; index < m; ++index) {
      const int first = order[index];
      const int second = order[(index + 1) % m];
      next_edges.push_back((rng() & 1) ? first * m + second : second * m + first);
    }
    set_edges(next_edges);
  }

  void initialize_general_factor() {
    std::vector<int> vertices(m);
    std::iota(vertices.begin(), vertices.end(), 0);
    std::shuffle(vertices.begin(), vertices.end(), rng);

    const int roll = int(rng() % 100);
    int component_count = roll < 35 ? 1 : roll < 70 ? 2 : roll < 90 ? 3 : 4;
    component_count = std::min(component_count, m);
    std::unordered_set<int> cut_set;
    while (cut_set.size() < size_t(component_count - 1)) {
      cut_set.insert(1 + int(rng() % (m - 1)));
    }
    std::vector<int> cuts(cut_set.begin(), cut_set.end());
    std::sort(cuts.begin(), cuts.end());
    cuts.push_back(m);

    std::vector<int> next_edges;
    next_edges.reserve(m);
    int begin = 0;
    for (int end : cuts) {
      const int length = end - begin;
      if (length == 1) {
        const int vertex = vertices[begin];
        next_edges.push_back(vertex * m + vertex);
      } else if (length == 2) {
        const int first = vertices[begin];
        const int second = vertices[begin + 1];
        next_edges.push_back(first * m + second);
        next_edges.push_back(second * m + first);
      } else {
        for (int offset = 0; offset < length; ++offset) {
          const int first = vertices[begin + offset];
          const int second = vertices[begin + (offset + 1) % length];
          next_edges.push_back((rng() & 1) ? first * m + second : second * m + first);
        }
      }
      begin = end;
    }
    set_edges(next_edges);
  }

  void initialize_code(const std::string& code) {
    if (code.size() != size_t(1 + 2 * n) || code[0] != 'o') {
      throw std::runtime_error("--incumbent is not a compact rot4 code of the target size");
    }
    const std::string alphabet = kAlphabet;
    std::vector<int> next_edges;
    next_edges.reserve(m);
    for (int row = 0; row < m; ++row) {
      for (int slot = 0; slot < 2; ++slot) {
        const size_t position = alphabet.find(code[1 + 2 * row + slot]);
        if (position == std::string::npos || int(position) >= n) {
          throw std::runtime_error("invalid character in --incumbent code");
        }
        if (int(position) < m) next_edges.push_back(row * m + int(position));
      }
    }
    set_edges(next_edges);
  }

  void prepare_lift_pool(int source_n, const std::string& source_code, size_t initial_rank) {
    if (n != source_n + 2 || source_n % 2 != 0) {
      throw std::runtime_error("a lift requires target n = source n + 2");
    }
    if (source_code.size() != size_t(1 + 2 * source_n) || source_code[0] != 'o') {
      throw std::runtime_error("the source is not a compact optimal configuration code");
    }

    const std::string alphabet = kAlphabet;
    const int source_m = source_n / 2;
    const int new_vertex = source_m;
    std::vector<int> old_edges;
    old_edges.reserve(source_m);
    for (int row = 0; row < source_m; ++row) {
      for (int slot = 0; slot < 2; ++slot) {
        const size_t position = alphabet.find(source_code[1 + 2 * row + slot]);
        if (position == std::string::npos) throw std::runtime_error("invalid character in source code");
        if (int(position) < source_m) old_edges.push_back(row * m + int(position));
      }
    }
    if (old_edges.size() != size_t(source_m)) {
      throw std::runtime_error("source code does not induce the expected 2-factor");
    }

    std::vector<std::vector<int>> candidates;
    candidates.push_back(old_edges);
    candidates.back().push_back(new_vertex * m + new_vertex);

    auto add_replacement = [&](int removed_index, const std::vector<int>& replacement) {
      std::vector<int> candidate;
      candidate.reserve(m);
      for (int index = 0; index < int(old_edges.size()); ++index) {
        if (index != removed_index) candidate.push_back(old_edges[index]);
      }
      candidate.insert(candidate.end(), replacement.begin(), replacement.end());
      candidates.push_back(std::move(candidate));
    };

    for (int index = 0; index < int(old_edges.size()); ++index) {
      const int first = old_edges[index] / m;
      const int second = old_edges[index] % m;
      if (first == second) {
        add_replacement(index, {first * m + new_vertex, new_vertex * m + first});
        continue;
      }
      for (int orientation = 0; orientation < 4; ++orientation) {
        const int first_arc = (orientation & 1) ? new_vertex * m + first : first * m + new_vertex;
        const int second_arc = (orientation & 2) ? second * m + new_vertex : new_vertex * m + second;
        add_replacement(index, {first_arc, second_arc});
      }
    }

    std::vector<std::pair<long long, std::vector<int>>> ranked;
    ranked.reserve(candidates.size());
    for (const auto& candidate : candidates) {
      set_edges(candidate);
      ranked.push_back({energy, candidate});
    }
    std::sort(ranked.begin(), ranked.end(), [](const auto& first, const auto& second) {
      return first.first < second.first;
    });
    lift_pool.clear();
    lift_pool.reserve(ranked.size());
    for (auto& [candidate_energy, candidate] : ranked) {
      (void)candidate_energy;
      lift_pool.push_back(std::move(candidate));
    }
    lift_cursor = initial_rank % lift_pool.size();
    set_edges(lift_pool[lift_cursor]);
    ++lift_cursor;
  }

  void initialize_portfolio() {
    if (!lift_pool.empty() && rng() % 4 == 0) {
      set_edges(lift_pool[lift_cursor % lift_pool.size()]);
      ++lift_cursor;
    } else if (rng() & 1) {
      initialize_hamiltonian();
    } else {
      initialize_general_factor();
    }
  }

  void refresh_conflict_weights() {
    for (int index = 0; index < m; ++index) {
      const int id = edges[index];
      const long long before = weighted_energy;
      remove_orbit(id);
      const long long score = before - weighted_energy;
      add_orbit(id);
      conflict_weights[index] = std::max(1LL, score);
    }
  }

  void recompute_weighted_energy() {
    weighted_energy = 0;
    for (const auto& [line, count] : line_counts) {
      if (count >= 3) weighted_energy += line_weight(line) * choose_three(count);
    }
  }

  void bump_violated_line_weights() {
    bool changed = false;
    for (const auto& [line, count] : line_counts) {
      if (count < 3) continue;
      int& weight = line_weights[line];
      if (weight == 0) weight = 1;
      if (weight < 64) {
        ++weight;
        weighted_energy += choose_three(count);
        changed = true;
      }
    }
    if (changed) return;
    for (auto& [line, weight] : line_weights) {
      (void)line;
      weight = 1 + (weight - 1) / 2;
    }
    recompute_weighted_energy();
  }

  int choose_conflict_edge() {
    const long long total = std::accumulate(conflict_weights.begin(), conflict_weights.end(), 0LL);
    long long choice = static_cast<long long>(rng() % total);
    for (int index = 0; index < m; ++index) {
      choice -= conflict_weights[index];
      if (choice < 0) return index;
    }
    return m - 1;
  }

  bool accept(long long delta, double temperature) {
    if (delta <= 0) return true;
    const double probability = std::exp(-double(delta) / temperature);
    return std::generate_canonical<double, 53>(rng) < probability;
  }

  bool replacement_is_valid(const std::vector<int>& indices, const std::vector<int>& next) const {
    if (indices.empty() || indices.size() != next.size()) return false;
    std::unordered_set<int> removed;
    std::unordered_set<int> added;
    for (int index : indices) {
      if (index < 0 || index >= m || !removed.insert(edges[index]).second) return false;
    }
    for (int id : next) {
      if (id < 0 || id >= m * m || !added.insert(id).second) return false;
      if (selected_orbit[id] && !removed.count(id)) return false;
    }
    return true;
  }

  bool apply_replacement(const std::vector<int>& indices, const std::vector<int>& next,
                         double temperature) {
    if (!replacement_is_valid(indices, next)) return false;
    std::vector<int> old;
    old.reserve(indices.size());
    for (int index : indices) old.push_back(edges[index]);

    const long long before = weighted_energy;
    for (int id : old) remove_orbit(id);
    for (int id : next) add_orbit(id);
    if (accept(weighted_energy - before, temperature)) {
      for (size_t offset = 0; offset < indices.size(); ++offset) edges[indices[offset]] = next[offset];
      return true;
    }
    for (int id : next) remove_orbit(id);
    for (int id : old) add_orbit(id);
    return false;
  }

  bool flip_move(int index, double temperature) {
    const int old = edges[index];
    const int first = old / m;
    const int second = old % m;
    if (first == second) return false;
    const int next = second * m + first;
    return apply_replacement({index}, {next}, temperature);
  }

  bool switch_move(int first_index, int second_index, double temperature) {
    if (first_index == second_index) return false;
    const int old_first = edges[first_index];
    const int old_second = edges[second_index];
    const int a = old_first / m;
    const int b = old_first % m;
    const int c = old_second / m;
    const int d = old_second % m;
    if (a == b || c == d) return false;
    if (a == c || a == d || b == c || b == d) return false;

    int first_u;
    int first_v;
    int second_u;
    int second_v;
    if (rng() & 1) {
      first_u = a;
      first_v = c;
      second_u = b;
      second_v = d;
    } else {
      first_u = a;
      first_v = d;
      second_u = b;
      second_v = c;
    }
    const int next_first = (rng() & 1) ? first_u * m + first_v : first_v * m + first_u;
    const int next_second = (rng() & 1) ? second_u * m + second_v : second_v * m + second_u;
    return apply_replacement({first_index, second_index}, {next_first, next_second}, temperature);
  }

  bool loop_splice_move(int preferred_index, double temperature) {
    int loop_index = -1;
    if (edges[preferred_index] / m == edges[preferred_index] % m) loop_index = preferred_index;
    for (int attempt = 0; loop_index < 0 && attempt < 16; ++attempt) {
      const int candidate = int(rng() % m);
      if (edges[candidate] / m == edges[candidate] % m) loop_index = candidate;
    }
    if (loop_index < 0) return false;

    const int vertex = edges[loop_index] / m;
    for (int attempt = 0; attempt < 24; ++attempt) {
      const int other_index = attempt == 0 ? preferred_index : int(rng() % m);
      if (other_index == loop_index) continue;
      const int other = edges[other_index];
      const int first = other / m;
      const int second = other % m;
      if (first == second || first == vertex || second == vertex) continue;
      const int next_first = (rng() & 1) ? vertex * m + first : first * m + vertex;
      const int next_second = (rng() & 1) ? vertex * m + second : second * m + vertex;
      return apply_replacement({loop_index, other_index}, {next_first, next_second}, temperature);
    }
    return false;
  }

  bool loop_collapse_move(int first_index, double temperature) {
    const int first_id = edges[first_index];
    const int first_a = first_id / m;
    const int first_b = first_id % m;
    if (first_a == first_b) return false;

    for (int attempt = 0; attempt < 32; ++attempt) {
      const int second_index = int(rng() % m);
      if (second_index == first_index) continue;
      const int second_id = edges[second_index];
      const int second_a = second_id / m;
      const int second_b = second_id % m;
      if (second_a == second_b) continue;

      int shared = -1;
      int outer_first = -1;
      int outer_second = -1;
      if (first_a == second_a && first_b != second_b) {
        shared = first_a;
        outer_first = first_b;
        outer_second = second_b;
      } else if (first_a == second_b && first_b != second_a) {
        shared = first_a;
        outer_first = first_b;
        outer_second = second_a;
      } else if (first_b == second_a && first_a != second_b) {
        shared = first_b;
        outer_first = first_a;
        outer_second = second_b;
      } else if (first_b == second_b && first_a != second_a) {
        shared = first_b;
        outer_first = first_a;
        outer_second = second_a;
      }
      if (shared < 0 || outer_first == outer_second) continue;
      const int loop = shared * m + shared;
      const int outer = (rng() & 1) ? outer_first * m + outer_second : outer_second * m + outer_first;
      return apply_replacement({first_index, second_index}, {loop, outer}, temperature);
    }
    return false;
  }

  bool loop_move(int preferred_index, double temperature) {
    if (rng() & 1) {
      if (loop_splice_move(preferred_index, temperature)) return true;
      return loop_collapse_move(preferred_index, temperature);
    }
    if (loop_collapse_move(preferred_index, temperature)) return true;
    return loop_splice_move(preferred_index, temperature);
  }

  bool three_edge_move(int first_index, double temperature) {
    std::array<int, 3> indices{first_index, -1, -1};
    std::array<int, 6> endpoints{};
    const int first_id = edges[first_index];
    endpoints[0] = first_id / m;
    endpoints[1] = first_id % m;
    if (endpoints[0] == endpoints[1]) return false;

    int selected = 1;
    for (int attempt = 0; selected < 3 && attempt < 64; ++attempt) {
      const int index = int(rng() % m);
      if (index == indices[0] || index == indices[1]) continue;
      const int id = edges[index];
      const int first = id / m;
      const int second = id % m;
      if (first == second) continue;
      bool disjoint = true;
      for (int used = 0; used < 2 * selected; ++used) {
        if (endpoints[used] == first || endpoints[used] == second) disjoint = false;
      }
      if (!disjoint) continue;
      indices[selected] = index;
      endpoints[2 * selected] = first;
      endpoints[2 * selected + 1] = second;
      ++selected;
    }
    if (selected < 3) return false;

    for (int attempt = 0; attempt < 12; ++attempt) {
      std::shuffle(endpoints.begin(), endpoints.end(), rng);
      std::vector<int> next;
      next.reserve(3);
      for (int pair = 0; pair < 3; ++pair) {
        const int first = endpoints[2 * pair];
        const int second = endpoints[2 * pair + 1];
        next.push_back((rng() & 1) ? first * m + second : second * m + first);
      }
      if (apply_replacement({indices[0], indices[1], indices[2]}, next, temperature)) return true;
    }
    return false;
  }

  bool four_edge_move(int first_index, double temperature) {
    std::array<int, 4> indices{first_index, -1, -1, -1};
    std::array<int, 8> endpoints{};
    const int first_id = edges[first_index];
    endpoints[0] = first_id / m;
    endpoints[1] = first_id % m;
    if (endpoints[0] == endpoints[1]) return false;

    int selected = 1;
    for (int attempt = 0; selected < 4 && attempt < 96; ++attempt) {
      const int index = int(rng() % m);
      bool repeated_index = false;
      for (int used = 0; used < selected; ++used) {
        if (index == indices[used]) repeated_index = true;
      }
      if (repeated_index) continue;

      const int id = edges[index];
      const int first = id / m;
      const int second = id % m;
      if (first == second) continue;
      bool disjoint = true;
      for (int used = 0; used < 2 * selected; ++used) {
        if (endpoints[used] == first || endpoints[used] == second) disjoint = false;
      }
      if (!disjoint) continue;
      indices[selected] = index;
      endpoints[2 * selected] = first;
      endpoints[2 * selected + 1] = second;
      ++selected;
    }
    if (selected < 4) return false;

    for (int attempt = 0; attempt < 24; ++attempt) {
      std::shuffle(endpoints.begin(), endpoints.end(), rng);
      std::vector<int> next;
      next.reserve(4);
      for (int pair = 0; pair < 4; ++pair) {
        const int first = endpoints[2 * pair];
        const int second = endpoints[2 * pair + 1];
        next.push_back((rng() & 1) ? first * m + second : second * m + first);
      }
      if (apply_replacement(
              {indices[0], indices[1], indices[2], indices[3]}, next,
              temperature)) {
        return true;
      }
    }
    return false;
  }

  void perturb_current(int count) {
    for (int move = 0; move < count; ++move) {
      const int first = int(rng() % m);
      const int kind = four_edge_percent > 0 &&
                               int(rng() % 100) < four_edge_percent
                           ? 4
                           : int(rng() % 4);
      if (kind == 0) flip_move(first, 1e9);
      else if (kind == 1) switch_move(first, int(rng() % m), 1e9);
      else if (kind == 2) loop_move(first, 1e9);
      else if (kind == 3) three_edge_move(first, 1e9);
      else four_edge_move(first, 1e9);
      if (energy < best_energy) {
        best_energy = energy;
        best_edges = edges;
      }
      if (energy == 0) break;
    }
  }

  bool run_until(Clock::time_point deadline, std::atomic<bool>& stop, SharedBest& shared,
                 int thread_index, int stagnation_ms, long long& iterations,
                 long long& restarts, long long& stagnation_restarts) {
    bool first_run = true;
    bool restart_from_incumbent = false;
    shared.publish(best_energy, best_edges, thread_index);
    if (best_energy == 0) {
      set_edges(best_edges);
      stop.store(true, std::memory_order_relaxed);
      return true;
    }
    while (Clock::now() < deadline && !stop.load(std::memory_order_relaxed)) {
      if (!first_run) {
        const auto incumbent = shared.snapshot();
        if ((restart_from_incumbent || restarts % 4 == 0) &&
            !incumbent.second.empty()) {
          set_edges(incumbent.second);
          perturb_current(8 + int(rng() % 17));
        } else {
          initialize_portfolio();
        }
      }
      first_run = false;
      restart_from_incumbent = false;
      ++restarts;
      shared.publish(best_energy, best_edges, thread_index);
      long long since_improvement = 0;
      long long next_breakout = 5000;
      auto last_improvement = Clock::now();

      for (long long step = 0; step < 250000 && Clock::now() < deadline; ++step) {
        if (stop.load(std::memory_order_relaxed) || energy == 0) break;
        if (step % 64 == 0) {
          if (stagnation_ms > 0 &&
              std::chrono::duration_cast<std::chrono::milliseconds>(
                  Clock::now() - last_improvement)
                      .count() >= stagnation_ms) {
            ++stagnation_restarts;
            restart_from_incumbent = true;
            break;
          }
          refresh_conflict_weights();
        }
        const double phase = double(step % 20000) / 20000.0;
        const double temperature = 0.25 + 4.75 * (1.0 - phase);
        const int first = choose_conflict_edge();
        const int kind = four_edge_percent > 0 &&
                                 int(rng() % 100) < four_edge_percent
                             ? 4
                             : [&] {
                                 const int roll = int(rng() % 100);
                                 return roll < 25 ? 0 : roll < 65 ? 1 : roll < 82 ? 2 : 3;
                               }();
        ++attempted_moves[kind];
        bool moved = false;
        if (kind == 0) moved = flip_move(first, temperature);
        else if (kind == 1) moved = switch_move(first, int(rng() % m), temperature);
        else if (kind == 2) moved = loop_move(first, temperature);
        else if (kind == 3) moved = three_edge_move(first, temperature);
        else moved = four_edge_move(first, temperature);
        if (moved) ++accepted_moves[kind];
        ++iterations;

        if (energy < best_energy) {
          best_energy = energy;
          best_edges = edges;
          since_improvement = 0;
          next_breakout = 5000;
          last_improvement = Clock::now();
          shared.publish(best_energy, best_edges, thread_index);
        } else if (moved) {
          ++since_improvement;
        }
        if (energy == 0) {
          shared.publish(0, edges, thread_index);
          stop.store(true, std::memory_order_relaxed);
          return true;
        }
        if (since_improvement >= next_breakout) {
          bump_violated_line_weights();
          refresh_conflict_weights();
          if (next_breakout % 15000 == 0) {
            const auto incumbent = shared.snapshot();
            if (!incumbent.second.empty() && incumbent.first + 4 < energy) {
              set_edges(incumbent.second);
              perturb_current(4 + int(rng() % 9));
              since_improvement = 0;
              next_breakout = 5000;
              continue;
            }
          }
          next_breakout += 5000;
        }
        if (since_improvement > 60000) break;
      }
    }
    return energy == 0;
  }

  std::string compact_code(const std::vector<int>& factor_edges) const {
    const std::string alphabet = kAlphabet;
    std::vector<std::vector<int>> rows(n);
    for (int id : factor_edges) {
      for (int point : orbit_points[id]) rows[point / n].push_back(point % n);
    }

    std::string code = "o";
    for (auto& row : rows) {
      std::sort(row.begin(), row.end());
      if (row.size() != 2) return "INVALID";
      code += alphabet[row[0]];
      code += alphabet[row[1]];
    }
    return code;
  }

  std::string compact_code() const { return compact_code(edges); }
};

std::string load_bundled_code(const std::string& filename, int n) {
  std::ifstream input(filename);
  if (!input) throw std::runtime_error("could not open solution bundle: " + filename);
  const std::string contents((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  const std::regex entry("\\b" + std::to_string(n) + "\\s*:\\s*\"([^\"]+)\"");
  std::smatch match;
  if (!std::regex_search(contents, match, entry)) {
    throw std::runtime_error("no bundled rot4 solution for n=" + std::to_string(n));
  }
  return match[1].str();
}

void usage(const char* program) {
  std::cerr << "Usage: " << program
            << " N SECONDS THREADS [--seed INTEGER] [--incumbent CODE]"
               " [--lift-from N] [--solutions PATH] [--stagnation-ms INTEGER]"
               " [--perturb-step INTEGER] [--four-edge-percent INTEGER]\n";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 4) {
    usage(argv[0]);
    return 2;
  }

  try {
    const int n = std::stoi(argv[1]);
    const int seconds = std::stoi(argv[2]);
    const int thread_count = std::stoi(argv[3]);
    uint64_t base_seed = uint64_t(Clock::now().time_since_epoch().count());
    int lift_from = -1;
    int stagnation_ms = 0;
    int perturb_step = 3;
    int four_edge_percent = 0;
    std::string incumbent_code;
    std::string solution_path = "optimal-solutions.generated.js";

    for (int index = 4; index < argc; ++index) {
      const std::string option = argv[index];
      if (index + 1 >= argc) throw std::runtime_error("missing value after " + option);
      if (option == "--seed") {
        base_seed = std::stoull(argv[++index]);
      } else if (option == "--incumbent") {
        incumbent_code = argv[++index];
      } else if (option == "--lift-from") {
        lift_from = std::stoi(argv[++index]);
      } else if (option == "--solutions") {
        solution_path = argv[++index];
      } else if (option == "--stagnation-ms") {
        stagnation_ms = std::stoi(argv[++index]);
      } else if (option == "--perturb-step") {
        perturb_step = std::stoi(argv[++index]);
      } else if (option == "--four-edge-percent") {
        four_edge_percent = std::stoi(argv[++index]);
      } else {
        throw std::runtime_error("unknown option: " + option);
      }
    }

    if (n % 2 != 0 || n < 6 || n > 90) throw std::runtime_error("n must be even and between 6 and 90");
    if (seconds < 1 || thread_count < 1) throw std::runtime_error("seconds and threads must be positive");
    if (stagnation_ms < 0) throw std::runtime_error("--stagnation-ms must be nonnegative");
    if (perturb_step < 0) throw std::runtime_error("--perturb-step must be nonnegative");
    if (four_edge_percent < 0 || four_edge_percent > 100) {
      throw std::runtime_error("--four-edge-percent must be between 0 and 100");
    }
    if (lift_from >= 0 && n != lift_from + 2) {
      throw std::runtime_error("--lift-from requires target n = source n + 2");
    }
    const std::string lift_code = lift_from >= 0 ? load_bundled_code(solution_path, lift_from) : "";

    std::atomic<bool> stop(false);
    const auto started = Clock::now();
    const auto deadline = started + std::chrono::seconds(seconds);
    SharedBest shared(started);
    std::vector<std::thread> threads;
    std::vector<long long> iterations(thread_count, 0);
    std::vector<long long> restarts(thread_count, 0);
    std::vector<long long> stagnation_restarts(thread_count, 0);
    std::vector<long long> initial(thread_count, 0);
    std::vector<long long> best(thread_count, 0);
    std::vector<std::array<long long, 5>> attempted(thread_count);
    std::vector<std::array<long long, 5>> accepted(thread_count);

    for (int thread_index = 0; thread_index < thread_count; ++thread_index) {
      threads.emplace_back([&, thread_index] {
        Search search(n, base_seed + 0x9e3779b97f4a7c15ULL * uint64_t(thread_index + 1));
        search.four_edge_percent = four_edge_percent;
        if (lift_from >= 0) {
          search.prepare_lift_pool(lift_from, lift_code, size_t(thread_index));
        }
        if (!incumbent_code.empty()) {
          search.initialize_code(incumbent_code);
          search.perturb_current(thread_index * perturb_step);
        } else if (lift_from < 0 && thread_index % 2 == 0) {
          search.initialize_hamiltonian();
        } else if (lift_from < 0) {
          search.initialize_general_factor();
        }
        initial[thread_index] = search.energy;
        search.run_until(deadline, stop, shared, thread_index, stagnation_ms,
                         iterations[thread_index], restarts[thread_index],
                         stagnation_restarts[thread_index]);
        best[thread_index] = search.best_energy;
        attempted[thread_index] = search.attempted_moves;
        accepted[thread_index] = search.accepted_moves;
      });
    }
    for (auto& thread : threads) thread.join();

    const long long total_iterations = std::accumulate(iterations.begin(), iterations.end(), 0LL);
    const long long total_restarts = std::accumulate(restarts.begin(), restarts.end(), 0LL);
    const long long total_stagnation_restarts =
        std::accumulate(stagnation_restarts.begin(), stagnation_restarts.end(), 0LL);
    const long long minimum = *std::min_element(best.begin(), best.end());
    const double mean_initial = std::accumulate(initial.begin(), initial.end(), 0.0) / thread_count;
    std::array<long long, 5> total_attempted{};
    std::array<long long, 5> total_accepted{};
    for (int thread_index = 0; thread_index < thread_count; ++thread_index) {
      for (int kind = 0; kind < 5; ++kind) {
        total_attempted[kind] += attempted[thread_index][kind];
        total_accepted[kind] += accepted[thread_index][kind];
      }
    }
    const auto global = shared.snapshot();
    Search encoder(n, 0);
    const std::string best_code = global.second.empty() ? "" : encoder.compact_code(global.second);
    std::cout << "n=" << n << " threads=" << thread_count << " seconds=" << seconds
              << " seed=" << base_seed << " initial_energy=" << mean_initial
              << " best_energy=" << std::min(minimum, global.first)
              << " iterations=" << total_iterations << " restarts=" << total_restarts
              << " stagnation_restarts=" << total_stagnation_restarts
              << " perturb_step=" << perturb_step
              << " four_edge_percent=" << four_edge_percent << "\n";
    std::cout << "moves=flip:" << total_accepted[0] << "/" << total_attempted[0]
              << ",switch:" << total_accepted[1] << "/" << total_attempted[1]
              << ",loop:" << total_accepted[2] << "/" << total_attempted[2]
              << ",three:" << total_accepted[3] << "/" << total_attempted[3]
              << ",four:" << total_accepted[4] << "/" << total_attempted[4] << "\n";
    for (const auto& event : shared.progress) {
      std::cout << "progress_ms=" << event.milliseconds << " best_energy=" << event.energy
                << " thread=" << event.thread << "\n";
    }
    if (!best_code.empty()) std::cout << "best_code=" << best_code << "\n";
    if (global.first == 0 && !best_code.empty()) std::cout << "solution=" << best_code << "\n";
    return global.first == 0 ? 0 : 1;
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << "\n";
    usage(argv[0]);
    return 2;
  }
}
