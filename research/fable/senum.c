/* Enumerate ALL Lemma-S survivors for given m; for each, count violating lines
 * (lines containing >=3 of the 4m points). Report: survivor count, mean/min
 * residual violations, count with zero violations (= true solutions).
 * Also mode "mcv": Monte Carlo of violating-line counts for random involutions.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#define MAXM 80
#define MAXPTS (4*MAXM)
static int m;
static uint8_t Gcd[512][512];
static int px[MAXPTS], py[MAXPTS], npts;
static long long g_orbits;

static inline uint64_t hash64(uint64_t k){ k^=k>>33;k*=0xff51afd7ed558ccdULL;k^=k>>33;k*=0xc4ceb9fe1a85ec53ULL;k^=k>>33;return k;}

static long long violating_lines(void){
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
    long long v=0; g_orbits=0;
    /* canonicalize violating lines under D4 to count orbits */
    static uint64_t seen[4096]; int ns=0;
    for(int e=0;e<top;e++) if(mcount[e]>=3){
        v++;
        int aa=(int)((mkey[e]>>40)&0xFFFFF)-256, bb=(int)((mkey[e]>>20)&0xFFFFF)-256;
        int64_t c=(int64_t)(mkey[e]&0xFFFFF)-(1<<19);
        /* D4 on (x,y): 8 maps; line a x + b y = c transforms accordingly */
        uint64_t best=~0ULL;
        int M[8][4]={{1,0,0,1},{-1,0,0,1},{1,0,0,-1},{-1,0,0,-1},{0,1,1,0},{0,-1,1,0},{0,1,-1,0},{0,-1,-1,0}};
        for(int t=0;t<8;t++){
            /* (x,y)->(m0 x+m1 y, m2 x+m3 y); line ax+by=c pulls back to a'(x)+... :
               substitute inverse; since all M orthogonal integer, inverse = transpose */
            int a2=M[t][0]*aa+M[t][2]*bb;
            int b2=M[t][1]*aa+M[t][3]*bb;
            int64_t c2=c;
            if(a2<0||(a2==0&&b2<0)){a2=-a2;b2=-b2;c2=-c2;}
            uint64_t k=((uint64_t)(a2+256)<<40)|((uint64_t)(b2+256)<<20)|(uint64_t)(c2+(1<<19));
            if(k<best)best=k;
        }
        int dup=0; for(int q=0;q<ns;q++) if(seen[q]==best){dup=1;break;}
        if(!dup && ns<4096){seen[ns++]=best; g_orbits++;}
    }
    return v;
}

static void build_points(int pr[][2], int npr, int fx){
    npts=0;
    if(fx>0){int a=2*fx-1;
        px[npts]=a;py[npts]=a;npts++; px[npts]=a;py[npts]=-a;npts++;
        px[npts]=-a;py[npts]=a;npts++; px[npts]=-a;py[npts]=-a;npts++;}
    static const int S[4][2]={{1,1},{1,-1},{-1,1},{-1,-1}};
    for(int t=0;t<npr;t++){
        int a=2*pr[t][0]-1,b=2*pr[t][1]-1;
        for(int s=0;s<4;s++){
            px[npts]=S[s][0]*b; py[npts]=S[s][1]*a; npts++;
            px[npts]=S[s][0]*a; py[npts]=S[s][1]*b; npts++;
        }
    }
}

static uint8_t lab[2*MAXM+4];
static int freeidx[MAXM+2], nfree;
static int prs[MAXM][2], nprs, fixpt;
static long long scount, zerocount; static double vsum, osum; static long long vmin;
static long long vhist[40];

static void rec(void){
    if(nfree==0){
        build_points(prs,nprs,fixpt);
        long long v=violating_lines();
        scount++; vsum+=v; osum+=g_orbits; if(v<vmin)vmin=v; if(v==0)zerocount++;
        if(v<40)vhist[v]++;
        return;
    }
    int i=freeidx[0];
    if(fixpt<0 && (m&1)){
        int L=2*i-1;
        if(!lab[L]){
            lab[L]=1; fixpt=i;
            int sv[MAXM+2]; memcpy(sv,freeidx,sizeof sv); int svn=nfree;
            memmove(freeidx,freeidx+1,(nfree-1)*sizeof(int)); nfree--;
            rec();
            memcpy(freeidx,sv,sizeof sv); nfree=svn;
            fixpt=-1; lab[L]=0;
        }
    }
    for(int k=1;k<nfree;k++){
        int j=freeidx[k];
        int d=j-i, s=i+j-1;
        if(d==s||lab[d]||lab[s]) continue;
        lab[d]=lab[s]=1;
        int sv[MAXM+2]; memcpy(sv,freeidx,sizeof sv); int svn=nfree;
        int nn=0; for(int q=0;q<nfree;q++) if(sv[q]!=i&&sv[q]!=j) freeidx[nn++]=sv[q];
        nfree=nn;
        prs[nprs][0]=i; prs[nprs][1]=j; nprs++;
        rec();
        nprs--;
        memcpy(freeidx,sv,sizeof sv); nfree=svn;
        lab[d]=lab[s]=0;
    }
}

static uint64_t rng_s=0x9E3779B97F4A7C15ULL;
static inline uint64_t xrand(void){ rng_s^=rng_s<<13; rng_s^=rng_s>>7; rng_s^=rng_s<<17; return rng_s; }

int main(int argc,char**argv){
    for(int a=0;a<512;a++)for(int b=0;b<512;b++){int x=a,y=b;while(y){int t=x%y;x=y;y=t;}Gcd[a][b]=x?x:1;}
    if(argc>=3 && !strcmp(argv[1],"senum")){
        m=atoi(argv[2]);
        nfree=m; for(int i=0;i<m;i++)freeidx[i]=i+1;
        memset(lab,0,sizeof lab); nprs=0; fixpt=-1;
        scount=0; vsum=0; osum=0; vmin=1LL<<60; zerocount=0; memset(vhist,0,sizeof vhist);
        rec();
        printf("m=%2d n=%3d S_survivors=%lld SOLUTIONS=%lld mean_resid_viol=%.3f mean_viol_ORBITS=%.3f min_resid_viol=%lld\n",
            m,2*m,scount,zerocount,scount?vsum/scount:0.0,scount?osum/scount:0.0,scount?vmin:-1);
        printf("   hist[0..14]:"); for(int i=0;i<15;i++)printf(" %lld",vhist[i]); printf("\n");
        fflush(stdout);
    } else if(argc>=4 && !strcmp(argv[1],"mcv")){
        m=atoi(argv[2]); long long K=atoll(argv[3]);
        double sum=0, orbsum=0; long long zero=0;
        for(long long it=0;it<K;it++){
            int idx[MAXM+1]; int cnt=0;
            for(int i=1;i<=m;i++)idx[cnt++]=i;
            int fx=-1;
            if(m&1){ int r=xrand()%cnt; fx=idx[r]; idx[r]=idx[--cnt]; }
            int pr[MAXM][2]; int np=0;
            while(cnt){
                int i=idx[0]; idx[0]=idx[--cnt];
                int r=xrand()%cnt; int j=idx[r]; idx[r]=idx[--cnt];
                pr[np][0]=i<j?i:j; pr[np][1]=i<j?j:i; np++;
            }
            build_points(pr,np,fx);
            long long v=violating_lines();
            sum+=v; orbsum+=g_orbits; if(!v)zero++;
        }
        printf("m=%d n=%d K=%lld mean_viol_lines=%.3f mean_viol_ORBITS=%.3f P(zero)=%.6g\n",m,2*m,K,sum/K,orbsum/K,(double)zero/K);
        fflush(stdout);
    }
    return 0;
}
