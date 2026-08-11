/* uk.c — fast decision procedure for U_K(m) = 0 vs > 0:
 * does a Lemma-S survivor exist with NO 3 points on any line whose
 * normalized coefficients satisfy max(|a|,|b|) <= K ?
 *
 * Specialization of dmin maxk <m> <K> 1 using Theorem 4 (FINDINGS 10.6):
 * instead of a generic line hash, keep one count array per direction
 * functional (a,b), a in {p,q}, b = +-partner, over values c = a*x + b*y.
 * Adding a point increments ~2*#families counters; prune on any count
 * reaching 3.  Families {0,1} and {1,1} are omitted (Theorem 3 / Lemma S:
 * they never violate for survivors).
 *
 * Usage: uk <m> <K> [jlo jhi]
 * Output: ESCAPE + sigma, or NONE (U_K > 0), per root branch.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXM 100
#define MAXD 160          /* max functionals: 2 per family, families ~ K^2*3/pi^2 */
#define MAXV (32*MAXM+64) /* |c| <= (p+q)(2m-1) <= 15*(2m-1) for K=8 */

static int m, K;
static int ndir; static int DA[MAXD], DB[MAXD];  /* functionals a*x + b*y */
static unsigned char cnt[MAXD][2*MAXV];          /* value counts, offset MAXV */
static int trail_d[1<<22], trail_v[1<<22]; static int tr_top;

static int used[MAXM+1], sigma[MAXM+1], fixed_used;
static unsigned char lab[2*MAXM+4];
static long long nodes; static int found; static int fsig[MAXM+1];
static int root_jlo=0, root_jhi=0, at_root=1;

static int gcd(int a,int b){ while(b){int t=a%b;a=b;b=t;} return a; }

/* add the 8 (or 4) points of an orbit; returns 0 on any 3-in-line (undo left to caller) */
static int add_orbit(int i,int j){
    int a=2*i-1, b=2*j-1;
    int xs[8], ys[8], np=0;
    if(i==j){ xs[0]=a;ys[0]=a; xs[1]=a;ys[1]=-a; xs[2]=-a;ys[2]=a; xs[3]=-a;ys[3]=-a; np=4; }
    else {
        static const int S[4][2]={{1,1},{1,-1},{-1,1},{-1,-1}};
        for(int s=0;s<4;s++){
            xs[np]=S[s][0]*b; ys[np]=S[s][1]*a; np++;
            xs[np]=S[s][0]*a; ys[np]=S[s][1]*b; np++;
        }
    }
    for(int t=0;t<np;t++){
        for(int d=0;d<ndir;d++){
            int v = DA[d]*xs[t] + DB[d]*ys[t] + MAXV;
            if(++cnt[d][v] >= 3){
                trail_d[tr_top]=d; trail_v[tr_top]=v; tr_top++;
                return 0;
            }
            trail_d[tr_top]=d; trail_v[tr_top]=v; tr_top++;
        }
    }
    return 1;
}
static void undo_to(int mark){
    while(tr_top>mark){ tr_top--; cnt[trail_d[tr_top]][trail_v[tr_top]]--; }
}

static void dfs(void){
    if(found) return;
    nodes++;
    int t=-1;
    for(int i=1;i<=m;i++) if(!used[i]){t=i;break;}
    if(t<0){ found=1; for(int i=1;i<=m;i++) fsig[i]=sigma[i]; return; }
    int was_root = at_root; at_root = 0;
    used[t]=1;
    if((!was_root || root_jhi==0 || (root_jlo<=1 && 1<=root_jhi)) && !fixed_used && (m&1)){
        int L=2*t-1;
        if(!lab[L]){
            lab[L]=1; fixed_used=1;
            int mk=tr_top;
            if(add_orbit(t,t)){ sigma[t]=t; dfs(); }
            undo_to(mk);
            fixed_used=0; lab[L]=0;
        }
    }
    for(int j=t+1;j<=m && !found;j++){
        if(used[j]) continue;
        if(was_root && root_jhi>0 && (j<root_jlo || j>root_jhi)) continue;
        int d=j-t, s=t+j-1;
        if(d==s||lab[d]||lab[s]) continue;
        lab[d]=lab[s]=1; used[j]=1;
        int mk=tr_top;
        if(add_orbit(t,j)){ sigma[t]=j; sigma[j]=t; dfs(); }
        undo_to(mk);
        used[j]=0; lab[d]=lab[s]=0;
    }
    used[t]=0;
}

int main(int argc,char**argv){
    if(argc<3){fprintf(stderr,"usage: %s <m> <K> [jlo jhi]\n",argv[0]);return 1;}
    m=atoi(argv[1]); K=atoi(argv[2]);
    if(argc>4){ root_jlo=atoi(argv[3]); root_jhi=atoi(argv[4]); }
    ndir=0;
    for(int q=2;q<=K;q++) for(int p=1;p<q;p++){
        if(gcd(p,q)!=1) continue;
        /* 4 directions of the family {p,q}: functionals (q,p),(q,-p),(p,q),(p,-q) */
        DA[ndir]=q; DB[ndir]=p;  ndir++;
        DA[ndir]=q; DB[ndir]=-p; ndir++;
        DA[ndir]=p; DB[ndir]=q;  ndir++;
        DA[ndir]=p; DB[ndir]=-q; ndir++;
    }
    if((2*K)*(2*m-1) >= MAXV){ fprintf(stderr,"value range overflow\n"); return 1; }
    memset(cnt,0,sizeof cnt); memset(lab,0,sizeof lab); memset(used,0,sizeof used);
    tr_top=0; nodes=0; found=0; fixed_used=0; at_root=1;
    dfs();
    printf("uk m=%d K=%d jr=[%d,%d] %s nodes=%lld\n", m, K, root_jlo, root_jhi,
        found?"ESCAPE":"NONE", nodes);
    if(found){ printf("   sigma:"); for(int i=1;i<=m;i++)printf(" %d",fsig[i]); printf("\n"); }
    return 0;
}
