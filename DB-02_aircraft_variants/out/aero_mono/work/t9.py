import sys, math; sys.dont_write_bytecode=True
exec(open('t7.py').read().split('e0,_=run(0)')[0])
def run3(h,toe,tw,cfac=0.5,alpha=10.0):
    cr_,mac_=cr,mac
    L=["SURFACE","Wing","10 1.0 28 1.0","YDUPLICATE","0.0"]
    for y,tt in ((0.0,0.0),(half,tw)):
        c=A.chord(y,half,cr,T); L+=["SECTION",f"{0.25*(cr-c):.5f} {y:.5f} 0.0 {c:.5f} {tt:.3f}"]
    if h>0:
        xle=0.25*(cr-ct); c1=ct*cfac; c2=c1*0.7
        L+=["SURFACE","WL","10 1.0 12 1.0","YDUPLICATE","0.0","SECTION",f"{xle+0.25*ct-0.25*c1:.5f} {half:.5f} 0.0 {c1:.5f} {toe:.3f}","SECTION",f"{xle+0.25*ct-0.25*c2:.5f} {half:.5f} {h:.5f} {c2:.5f} {toe:.3f}"]
    p=A.WORK/"x.avl"; A.write_avl(p,S,B,T,L); r=A.run_case(p,alpha,"z")
    return r["CL"]**2/(math.pi*ar*r["CDi"])
for tw in (-2,0,2,4,6):
    print("tip twist",tw,"no wl %.4f"%run3(0,0,tw), [ (h, max(round(run3(h,toe,tw),4) for toe in (0,1,2,3,4,6))) for h in (0.091,0.1365)])
