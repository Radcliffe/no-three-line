/* dmin.c — exact minimum residual defect D(m) over Lemma-S survivors,
 * by branch-and-bound with an incremental violating-line count.
 *
 * D(m) = min over involutions sigma of {1..m} with (m mod 2) fixed points
 *        and pairwise-distinct Lemma-S labels, of the number of lines
 *        containing >= 3 of the 4m points (doubled-odd model, see FINDINGS.md).
 *
 * Modes:
 *   dmin <m> [ub]            exact D(m) over all lines; optional initial upper bound
 *                            (bound is exclusive: search proves D(m) < ub or reports min found)
 *   fam  <m> <A> <B> [ub]    same but only count lines whose normalized (|a|,|b|)
 *                            equals {A,B} (line a*x+b*y=c, gcd-reduced).
 *                            A=B=0: all lines. A=-1: central lines only (c==0).
 *   famx <m> <A> <B> [ub]    like fam but EXCLUDE central lines from the count.
 *
 * Output: D(m), argmin sigma, node count. Validate against senum for m<=20.
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

static int32_t head[HSIZE];
static uint64_t ekey[POOL];
static int32_t enext[POOL];
static uint8_t ecnt[POOL];
static int32_t pool_top;

typedef struct { int32_t e; uint32_t b; uint8_t fresh; } TR;
static TR trail[1<<22];
static int32_t tr_top;

static long long nodes, leaves;
static int best;                 /* current best (min) violating-line count */
static int viol;                 /* current count of lines with >=3 points */
static int best_sigma[MAXM+1];
static int have_best;

/* family filter */
static int famA=0, famB=0;       /* 0,0 = all; -1 = central only */
static int fam_exclude_central=0;
static int maxK=0;               /* >0: count only lines with max(|a|,|b|) <= maxK */
static int escK=0;               /* >0: lines with max(|a|,|b|) <= escK are HARD
                                    (3 points = prune); all lines counted in viol */

static inline uint64_t hash64(uint64_t k){ k ^= k>>33; k *= 0xff51afd7ed558ccdULL; k ^= k>>33; k *= 0xc4ceb9fe1a85ec53ULL; k ^= k>>33; return k; }

/* add lines from new point to all existing; bump viol on 2->3 transitions.
 * returns 0 iff viol has reached best (prune). */
static inline int add_point(int xi, int yi){
    for(int k=0;k<npts;k++){
        int dx = px[k]-xi, dy = py[k]-yi;
        int adx = dx<0?-dx:dx, ady = dy<0?-dy:dy;
        int g = Gcd[adx][ady];
        int a = dy/g, b = -dx/g;
        if(a<0 || (a==0 && b<0)){ a=-a; b=-b; }
        int64_t c = (int64_t)a*xi + (int64_t)b*yi;
        if(maxK){
            int aa=a<0?-a:a, bb=b<0?-b:b;
            if((aa>bb?aa:bb) > maxK) continue;
        }
        else if(famA==-1){ if(c!=0) continue; }
        else if(famA||famB){
            int aa=a<0?-a:a, bb=b<0?-b:b;
            int lo=aa<bb?aa:bb, hi=aa<bb?bb:aa;
            int flo=famA<famB?famA:famB, fhi=famA<famB?famB:famA;
            if(lo!=flo||hi!=fhi) continue;
            if(fam_exclude_central && c==0) continue;
        } else if(fam_exclude_central && c==0) continue;
        uint64_t key = ((uint64_t)(a+256)<<40) | ((uint64_t)(b+256)<<20) | (uint64_t)(c+(1<<19));
        uint32_t bkt = (uint32_t)(hash64(key) & HMASK);
        int32_t e = head[bkt];
        while(e>=0 && ekey[e]!=key) e = enext[e];
        if(e>=0){
            ecnt[e]++;
            if(ecnt[e]==3){
                if(escK){
                    int aa=a<0?-a:a, bb=b<0?-b:b;
                    if((aa>bb?aa:bb) <= escK){
                        trail[tr_top].e=e; trail[tr_top].fresh=0; tr_top++;
                        viol++;
                        return 0; /* hard family violated: prune */
                    }
                }
                viol++;
            }
            trail[tr_top].e=e; trail[tr_top].fresh=0; tr_top++;
        } else {
            e = pool_top++;
            ekey[e]=key; ecnt[e]=1; enext[e]=head[bkt]; head[bkt]=e;
            trail[tr_top].e=e; trail[tr_top].b=bkt; trail[tr_top].fresh=1; tr_top++;
        }
    }
    px[npts]=xi; py[npts]=yi; npts++;
    return viol < best;
}

static inline void undo_to(int32_t mark, int npts_mark){
    while(tr_top>mark){
        tr_top--;
        TR *t=&trail[tr_top];
        if(t->fresh){ head[t->b]=enext[t->e]; pool_top--; }
        else { if(ecnt[t->e]==3) viol--; ecnt[t->e]--; }
    }
    npts = npts_mark;
}

static int add_orbit(int i,int j){
    int a=2*i-1, b=2*j-1;
    if(i==j){
        if(!add_point(a,a)) return 0;
        if(!add_point(a,-a)) return 0;
        if(!add_point(-a,a)) return 0;
        if(!add_point(-a,-a)) return 0;
        return 1;
    }
    static const int S[4][2]={{1,1},{1,-1},{-1,1},{-1,-1}};
    for(int s=0;s<4;s++){
        if(!add_point(S[s][0]*b, S[s][1]*a)) return 0;
        if(!add_point(S[s][0]*a, S[s][1]*b)) return 0;
    }
    return 1;
}

static uint8_t lab[2*MAXM+4];
static int used[MAXM+1], sigma[MAXM+1], fixed_used;
static int root_jlo=0, root_jhi=0, at_root=1; /* first decision: partner j in [jlo,jhi]; j==1 means the fixed option */

static void dfs(void){
    nodes++;
    int t=-1;
    for(int i=1;i<=m;i++) if(!used[i]){t=i;break;}
    if(t<0){
        leaves++;
        if(viol<best){
            best=viol; have_best=1;
            for(int i=1;i<=m;i++) best_sigma[i]=sigma[i];
        }
        return;
    }
    int was_root = at_root; at_root = 0;
    used[t]=1;
    if((!was_root || root_jhi==0 || (root_jlo<=1 && 1<=root_jhi)) && !fixed_used && (m&1)){
        int L=2*t-1;
        if(!lab[L]){
            lab[L]=1; fixed_used=1;
            int32_t mk=tr_top; int npm=npts;
            if(add_orbit(t,t)){ sigma[t]=t; dfs(); }
            undo_to(mk,npm);
            fixed_used=0; lab[L]=0;
        }
    }
    for(int j=t+1;j<=m;j++){
        if(used[j]) continue;
        if(was_root && root_jhi>0 && (j<root_jlo || j>root_jhi)) continue;
        int d=j-t, s=t+j-1;
        if(d==s||lab[d]||lab[s]) continue;
        lab[d]=lab[s]=1; used[j]=1;
        int32_t mk=tr_top; int npm=npts;
        if(add_orbit(t,j)){ sigma[t]=j; sigma[j]=t; dfs(); }
        undo_to(mk,npm);
        used[j]=0; lab[d]=lab[s]=0;
    }
    used[t]=0;
}

int main(int argc,char**argv){
    for(int a=0;a<512;a++)for(int b=0;b<512;b++){
        int x=a,y=b; while(y){int t=x%y;x=y;y=t;} Gcd[a][b]=x?x:1;
    }
    if(argc<3){fprintf(stderr,"usage: %s dmin|fam|famx <m> [args]\n",argv[0]);return 1;}
    const char*mode=argv[1];
    if(!strcmp(mode,"dmin")){
        m=atoi(argv[2]);
        best = argc>3?atoi(argv[3]):1<<30;
        if(argc>5){ root_jlo=atoi(argv[4]); root_jhi=atoi(argv[5]); }
    } else if(!strcmp(mode,"fam")||!strcmp(mode,"famx")){
        m=atoi(argv[2]); famA=atoi(argv[3]); famB=atoi(argv[4]);
        best = argc>5?atoi(argv[5]):1<<30;
        fam_exclude_central = !strcmp(mode,"famx");
    } else if(!strcmp(mode,"maxk")){
        m=atoi(argv[2]); maxK=atoi(argv[3]);
        best = argc>4?atoi(argv[4]):1<<30;
        if(argc>6){ root_jlo=atoi(argv[5]); root_jhi=atoi(argv[6]); }
    } else if(!strcmp(mode,"esc")){
        m=atoi(argv[2]); escK=atoi(argv[3]);
        best = argc>4?atoi(argv[4]):1<<30;
        if(argc>6){ root_jlo=atoi(argv[5]); root_jhi=atoi(argv[6]); }
    } else { fprintf(stderr,"bad mode\n"); return 1; }
    memset(head,-1,sizeof head);
    memset(lab,0,sizeof lab); memset(used,0,sizeof used);
    npts=0; pool_top=0; tr_top=0; nodes=0; leaves=0; viol=0; fixed_used=0; have_best=0;
    clock_t t0=clock();
    dfs();
    double el=(double)(clock()-t0)/CLOCKS_PER_SEC;
    printf("mode=%s m=%2d n=%3d famA=%d famB=%d exc=%d K=%d eK=%d jr=[%d,%d] D=%d nodes=%lld leaves=%lld time=%.2fs%s\n",
        mode,m,2*m,famA,famB,fam_exclude_central,maxK,escK,root_jlo,root_jhi,have_best?best:-1,nodes,leaves,el,
        have_best?"":" (no leaf below initial bound)");
    if(have_best){
        printf("   argmin sigma:"); for(int i=1;i<=m;i++)printf(" %d",best_sigma[i]); printf("\n");
    }
    fflush(stdout);
    return 0;
}
