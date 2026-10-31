import sys, math; sys.dont_write_bytecode=True
exec(open('t7.py').read().split('e0,_=run(0)')[0])
def run2(h,toe,cfac,cant=0.0,ctop=0.7,alpha=10.0):
    surf=A._surface_wing("Wing",S,B,T,nspan=28,nchord=10)
    xle=0.25*(cr-ct); c1=ct*cfac; c2=c1*ctop
    dy=h*math.sin(math.radians(cant)); dz=h*math.cos(math.radians(cant))
    surf+=["SURFACE","WL","10 1.0 12 1.0","YDUPLICATE","0.0","SECTION",f"{xle+0.25*ct-0.25*c1:.5f} {half:.5f} 0.0 {c1:.5f} {toe:.3f}","SECTION",f"{xle+0.25*ct-0.25*c2:.5f} {half+dy:.5f} {dz:.5f} {c2:.5f} {toe:.3f}"]
    p=A.WORK/"x.avl"; A.write_avl(p,S,B,T,surf); r=A.run_case(p,alpha,"y")
    return r["CL"]**2/(math.pi*ar*r["CDi"]), r
e0=run(0)[0]
for h in (0.091,0.1365,0.182):
  for cfac in (0.25,0.5,1.0):
    best=max(((run2(h,toe,cfac)[0]-e0,toe) for toe in (-1,0,1,2,3,4)))
    print("h/b %.3f cfac %.2f (c=%.3f) best de %.4f at toe %d"%(h/B,cfac,ct*cfac,best[0],best[1]))
# cant
for cant in (0,15,30,45):
    print("cant",cant,[round(run2(0.1365,toe,0.5,cant)[0]-e0,4) for toe in (0,1,2)])
