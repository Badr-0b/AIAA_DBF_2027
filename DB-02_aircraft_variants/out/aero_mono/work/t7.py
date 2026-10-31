import sys, math; sys.dont_write_bytecode=True
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src\aero_mono")
import avl_tools as A
S,B,T=0.9,1.82,0.7; half=B/2; cr,mac=A.planform(S,B,T); ct=A.chord(half,half,cr,T); ar=B*B/S
def run(h,toe=0.0,cant=0.0,ctop=0.7,nsp=12,nch=10,tag="x"):
    surf=A._surface_wing("Wing",S,B,T,nspan=28,nchord=10)
    if h>0:
        xle=0.25*(cr-ct)
        L=["SURFACE","WL",f"{nch} 1.0 {nsp} 1.0","YDUPLICATE","0.0"]
        dy=h*math.sin(math.radians(cant)); dz=h*math.cos(math.radians(cant))
        c2=ct*ctop
        L+=["SECTION",f"{xle:.5f} {half:.5f} 0.0 {ct:.5f} {toe:.3f}","SECTION",f"{xle+0.25*ct-0.25*c2:.5f} {half+dy:.5f} {dz:.5f} {c2:.5f} {toe:.3f}"]
        surf+=L
    p=A.WORK/"x.avl"; A.write_avl(p,S,B,T,surf)
    r=A.run_case(p,10.0,tag)
    return r["CL"]**2/(math.pi*ar*r["CDi"]), r
e0,_=run(0)
print("base e",e0)
for h in (0.0455,0.091,0.1365,0.182,0.364):
    row=[]
    for toe in (-6,-3,0,3,6):
        e,_=run(h,toe); row.append(round(e-e0,4))
    print("h/b %.3f"%(h/B), row)
