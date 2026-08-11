/* Exhaustive search for fully-symmetric (D4) no-three-in-line configurations.
 *
 * Model: even n = 2m. Involution sigma on {1..m}, #fixed = m mod 2 (0 or 1).
 * Points (doubled-odd coords): { (+-(2*sigma(i)-1), +-(2i-1)) }.
 * Search: assign orbits one row-index at a time; incremental line-count hash
 * with strict LIFO undo (chained buckets, head insertion, stack allocator).
 *
 * Modes:
 *   search  <m> [seconds]     exhaustive DFS for one m (0 seconds = no limit)
 *   scan    <mmax> [seconds]  loop m=1..mmax
 *   gcount  <mmax>            count Lemma-S survivors (slope+-1 labels distinct)
 *   mc      <m> <samples>     Monte Carlo: collinear-triple stats for random involutions
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define MAXM 80
#define MAXPTS (4*MAXM)
#define HBITS 21
#define HSIZE (1u<<HBITS)
#define HMASK (HSIZE-1)
#define POOL  (1u<<22)

static int m, npts;
static int px[MAXPTS], py[MAXPTS];

static uint8_t Gcd[512][512];
static inline int red(int v){ return v; }

/* hash table: chained, LIFO discipline */
static int32_t head[HSIZE];
static uint64_t ekey[POOL];
static int32_t enext[POOL];
static uint8_t ecnt[POOL];
static int32_t pool_top;

/* trail: positive entry idx = increment; negative-1-idx = fresh insertion (bucket b stored) */
typedef struct { int32_t e; uint32_t b; uint8_t fresh; } TR;
static TR trail[1<<22];
static int32_t tr_top;

static uint64_t nodes;
static long long solutions;
static double t_limit; static clock_t t0; static int timed_out;
static int sol_sigma_store[64][MAXM+1]; /* store up to 64 solutions */

static inline uint64_t hash64(uint64_t k){ k ^= k>>33; k *= 0xff51afd7ed558ccdULL; k ^= k>>33; k *= 0xc4ceb9fe1a85ec53ULL; k ^= k>>33; return k; }

static inline int add_pairs_with_point(int xi, int yi){
    /* line through new point (xi,yi) and each existing point; returns 0 on conflict */
    for(int k=0;k<npts;k++){
        int dx = px[k]-xi, dy = py[k]-yi;
        int adx = dx<0?-dx:dx, ady = dy<0?-dy:dy;
        int g = Gcd[adx][ady];
        int a = dy/g, b = -dx/g;
        if(a<0 || (a==0 && b<0)){ a=-a; b=-b; }
        int64_t c = (int64_t)a*xi + (int64_t)b*yi;
        uint64_t key = ((uint64_t)(a+256)<<40) | ((uint64_t)(b+256)<<20) | (uint64_t)(c+ (1<<19));
        uint32_t bkt = (uint32_t)(hash64(key) & HMASK);
        int32_t e = head[bkt];
        while(e>=0 && ekey[e]!=key) e = enext[e];
        if(e>=0){
            if(++ecnt[e] >= 3){ /* conflict; count already bumped -> record then fail */
                trail[tr_top].e=e; trail[tr_top].fresh=0; tr_top++;
                return 0;
            }
            trail[tr_top].e=e; trail[tr_top].fresh=0; tr_top++;
        } else {
            e = pool_top++;
            ekey[e]=key; ecnt[e]=1; enext[e]=head[bkt]; head[bkt]=e;
            trail[tr_top].e=e; trail[tr_top].b=bkt; trail[tr_top].fresh=1; tr_top++;
        }
    }
    px[npts]=xi; py[npts]=yi; npts++;
    return 1;
}

static inline void undo_to(int32_t mark, int npts_mark){
    while(tr_top>mark){
        tr_top--;
        TR *t=&trail[tr_top];
        if(t->fresh){ head[t->b]=enext[t->e]; pool_top--; }
        else ecnt[t->e]--;
    }
    npts = npts_mark;
}

/* add all points of orbit for pair (i,j), i<=j (i==j -> fixed, 4 points). 1=ok */
static int add_orbit(int i,int j){
    int a=2*i-1, b=2*j-1;
    if(i==j){
        if(!add_pairs_with_point(a,a)) return 0;
        if(!add_pairs_with_point(a,-a)) return 0;
        if(!add_pairs_with_point(-a,a)) return 0;
        if(!add_pairs_with_point(-a,-a)) return 0;
        return 1;
    }
    static const int S[4][2]={{1,1},{1,-1},{-1,1},{-1,-1}};
    for(int s=0;s<4;s++){
        if(!add_pairs_with_point(S[s][0]*b, S[s][1]*a)) return 0;
        if(!add_pairs_with_point(S[s][0]*a, S[s][1]*b)) return 0;
    }
    return 1;
}

static int used[MAXM+1], sigma[MAXM+1], fixed_used;
static int order_desc; /* 1: branch from largest free index */
static int root_jlo=0, root_jhi=0, at_root=1; /* restrict first decision: j in [jlo,jhi]; j==1 means fixed */

static void dfs(void){
    if(timed_out) return;
    if((++nodes & 0xFFFF)==0 && t_limit>0){
        if((double)(clock()-t0)/CLOCKS_PER_SEC > t_limit){ timed_out=1; return; }
    }
    int t=-1;
    if(order_desc){ for(int i=m;i>=1;i--) if(!used[i]){t=i;break;} }
    else          { for(int i=1;i<=m;i++) if(!used[i]){t=i;break;} }
    if(t<0){
        if(solutions<64) for(int i=1;i<=m;i++) sol_sigma_store[solutions][i]=sigma[i];
        solutions++;
        return;
    }
    int was_root = at_root; at_root = 0;
    used[t]=1;
    /* fixed option */
    if((!was_root || (root_jlo<=1 && 1<=root_jhi) || root_jhi==0) && !fixed_used && (m&1)){
        int32_t mk=tr_top; int npm=npts;
        fixed_used=1;
        if(add_orbit(t,t)){ sigma[t]=t; dfs(); }
        fixed_used=0;
        undo_to(mk,npm);
    }
    for(int j=1;j<=m;j++){
        if(used[j]) continue;
        if(was_root && root_jhi>0 && (j<root_jlo || j>root_jhi)) continue;
        used[j]=1;
        int32_t mk=tr_top; int npm=npts;
        int lo = t<j?t:j, hi = t<j?j:t;
        if(add_orbit(lo,hi)){ sigma[t]=j; sigma[j]=t; dfs(); }
        undo_to(mk,npm);
        used[j]=0;
        if(timed_out) break;
    }
    used[t]=0;
}

static void run_search(int mm, double secs, int quiet){
    m=mm; npts=0; pool_top=0; tr_top=0; nodes=0; solutions=0; timed_out=0; fixed_used=0; at_root=1;
    memset(head,-1,sizeof head);
    memset(used,0,sizeof used);
    t_limit=secs; t0=clock();
    dfs();
    double el=(double)(clock()-t0)/CLOCKS_PER_SEC;
    printf("n=%3d m=%3d nodes=%14llu solutions=%lld time=%8.2fs %s\n",
        2*mm, mm, (unsigned long long)nodes, solutions, el, timed_out?"TIMEOUT-INCOMPLETE":"COMPLETE");
    if(!quiet) for(long long s=0;s<solutions && s<64;s++){
        printf("   sigma:"); for(int i=1;i<=mm;i++) printf(" %d",sol_sigma_store[s][i]); printf("\n");
    }
    fflush(stdout);
}

/* ---- Lemma-S survivor count: labels {j-i}u{i+j-1}u{2i-1(fixed)} distinct ---- */
static long long gcount_total;
static uint8_t lab_used[2*MAXM+2];
static void grec(int freecnt, int minfree, int fx){
    if(freecnt==0){ gcount_total++; return; }
    /* find smallest free */
    /* we track free set in an array */
    extern int gfree[]; /* fwd */
    (void)minfree;(void)fx;
}
/* simpler explicit implementation */
static int gfreeArr[MAXM+2];
static long long grec2(int cnt, int fx){
    if(cnt==0) return 1;
    long long tot=0;
    int i=gfreeArr[0];
    if(!fx && (m&1)){
        int L=2*i-1;
        if(!lab_used[L]){
            lab_used[L]=1;
            int tmp[MAXM+2]; memcpy(tmp,gfreeArr,sizeof tmp);
            memmove(gfreeArr,gfreeArr+1,cnt*sizeof(int));
            tot+=grec2(cnt-1,1);
            memcpy(gfreeArr,tmp,sizeof tmp);
            lab_used[L]=0;
        }
    }
    for(int k=1;k<cnt;k++){
        int j=gfreeArr[k];
        int d=j-i, s=i+j-1;
        if(lab_used[d]||lab_used[s]||d==s) continue;
        lab_used[d]=lab_used[s]=1;
        int tmp[MAXM+2]; memcpy(tmp,gfreeArr,sizeof tmp);
        for(int q=k;q<cnt-1;q++) gfreeArr[q]=gfreeArr[q+1]; /* remove j */
        memmove(gfreeArr,gfreeArr+0,0);
        for(int q=0;q<cnt-2;q++) gfreeArr[q]=gfreeArr[q+1]==0?gfreeArr[q+1]:gfreeArr[q+1]; /* placeholder */
        /* redo properly: rebuild free list without i and j */
        memcpy(gfreeArr,tmp,sizeof tmp);
        int nf=0; int arr2[MAXM+2];
        for(int q=0;q<cnt;q++) if(tmp[q]!=i && tmp[q]!=j) arr2[nf++]=tmp[q];
        memcpy(gfreeArr,arr2,nf*sizeof(int));
        tot+=grec2(cnt-2,fx);
        memcpy(gfreeArr,tmp,sizeof tmp);
        lab_used[d]=lab_used[s]=0;
    }
    return tot;
}

/* ---- Monte Carlo ---- */
static uint64_t rng_s=88172645463325252ULL;
static inline uint64_t xrand(void){ rng_s^=rng_s<<13; rng_s^=rng_s>>7; rng_s^=rng_s<<17; return rng_s; }

static long long count_triples(void){
    /* count collinear triples among current npts points: sum over lines C(k,2)>=... 
       We count lines via fresh hashing (slow path fine for MC). Return #lines with k>=3 weighted? 
       Return total collinear triples = sum C(k,3). */
    static uint64_t keys[MAXPTS*MAXPTS/2]; static int kcnt;
    (void)keys;(void)kcnt;
    /* use a small local hash */
    #define MHB 18
    static int32_t mhead[1<<MHB]; static uint64_t mkey[1<<20]; static int mcount[1<<20]; static int32_t mnext[1<<20];
    memset(mhead,-1,sizeof mhead);
    int top=0;
    for(int a=0;a<npts;a++)for(int b=a+1;b<npts;b++){
        int dx=px[b]-px[a], dy=py[b]-py[a];
        int adx=dx<0?-dx:dx, ady=dy<0?-dy:dy;
        int g=Gcd[adx][ady];
        int aa=dy/g, bb=-dx/g;
        if(aa<0||(aa==0&&bb<0)){aa=-aa;bb=-bb;}
        int64_t c=(int64_t)aa*px[a]+(int64_t)bb*py[a];
        uint64_t key=((uint64_t)(aa+256)<<40)|((uint64_t)(bb+256)<<20)|(uint64_t)(c+(1<<19));
        uint32_t bk=(uint32_t)(hash64(key)&((1u<<MHB)-1));
        int32_t e=mhead[bk];
        while(e>=0&&mkey[e]!=key)e=mnext[e];
        if(e>=0)mcount[e]++;
        else{e=top++;mkey[e]=key;mcount[e]=1;mnext[e]=mhead[bk];mhead[bk]=e;}
    }
    /* mcount[e] = C(k,2) pairs on that line; recover k: k=(1+sqrt(1+8p))/2 */
    long long triples=0;
    for(int e=0;e<top;e++){
        long long p=mcount[e];
        if(p>=3){ /* k>=3 */
            long long k=1; while(k*(k-1)/2<p)k++;
            triples += k*(k-1)*(k-2)/6;
        }
    }
    return triples;
}

int main(int argc,char**argv){
    for(int a=0;a<512;a++)for(int b=0;b<512;b++){
        int x=a,y=b; while(y){int t=x%y;x=y;y=t;} Gcd[a][b]=x?x:1;
    }
    if(argc<2){fprintf(stderr,"usage: %s search|scan|gcount|mc ...\n",argv[0]);return 1;}
    if(!strcmp(argv[1],"search")){
        int mm=atoi(argv[2]); double s=argc>3?atof(argv[3]):0;
        order_desc = argc>4?atoi(argv[4]):1;
        if(argc>6){ root_jlo=atoi(argv[5]); root_jhi=atoi(argv[6]); }
        run_search(mm,s,0);
    } else if(!strcmp(argv[1],"scan")){
        int mmax=atoi(argv[2]); double s=argc>3?atof(argv[3]):0;
        order_desc = argc>4?atoi(argv[4]):1;
        for(int mm=1;mm<=mmax;mm++) run_search(mm,s,1);
    } else if(!strcmp(argv[1],"gcount")){
        int mmax=atoi(argv[2]);
        for(int mm=1;mm<=mmax;mm++){
            m=mm; memset(lab_used,0,sizeof lab_used);
            for(int i=0;i<mm;i++)gfreeArr[i]=i+1;
            long long c=grec2(mm,0);
            printf("m=%2d n=%3d lemmaS_survivors=%lld\n",mm,2*mm,c);
            fflush(stdout);
        }
    } else if(!strcmp(argv[1],"mc")){
        int mm=atoi(argv[2]); long long K=atoll(argv[3]);
        m=mm;
        long long zero=0; double sum=0, sumsq=0;
        for(long long it=0;it<K;it++){
            /* random involution with forced fixed-count */
            int idx[MAXM+1]; int cnt=0;
            for(int i=1;i<=mm;i++)idx[cnt++]=i;
            npts=0; pool_top=0; tr_top=0;
            memset(head,-1,sizeof head);
            int fx=-1;
            if(mm&1){ int r=xrand()%cnt; fx=idx[r]; idx[r]=idx[--cnt]; }
            /* points */
            npts=0;
            if(fx>0){int a=2*fx-1; px[npts]=a;py[npts]=a;npts++; px[npts]=a;py[npts]=-a;npts++; px[npts]=-a;py[npts]=a;npts++; px[npts]=-a;py[npts]=-a;npts++;}
            while(cnt){
                int i=idx[0]; idx[0]=idx[--cnt];
                int r=xrand()%cnt; int j=idx[r]; idx[r]=idx[--cnt];
                int a=2*(i<j?i:j)-1,b=2*(i<j?j:i)-1;
                static const int S[4][2]={{1,1},{1,-1},{-1,1},{-1,-1}};
                for(int s=0;s<4;s++){
                    px[npts]=S[s][0]*b; py[npts]=S[s][1]*a; npts++;
                    px[npts]=S[s][0]*a; py[npts]=S[s][1]*b; npts++;
                }
            }
            long long t=count_triples();
            if(t==0)zero++;
            sum+=t; sumsq+=(double)t*t;
        }
        double mean=sum/K, var=sumsq/K-mean*mean;
        printf("m=%d n=%d samples=%lld mean_triples=%.3f sd=%.3f P(zero)=%.6g\n",
            mm,2*mm,K,mean,var>0?__builtin_sqrt(var):0,(double)zero/K);
    }
    return 0;
}
