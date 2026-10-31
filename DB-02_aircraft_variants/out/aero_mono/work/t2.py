import sys; sys.dont_write_bytecode=True
sys.path.insert(0, r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src\aero_mono")
import avl_tools as A
S,b=0.9,1.82
for d,x0 in ((0.02,-0.3),(0.1,-0.3),(0.22,-0.3),(0.22,0.0)):
    p=A.WORK/"m2.avl"
    body=A._body("fus",1.05,d,x0=x0,z0=0.0)
    A.write_avl(p,S,b,0.7,A._surface_wing("Wing",S,b,0.7),body)
    r=A.run_case(p,4.0); print(d,x0,{k:round(v,4) for k,v in r.items() if k!='strips'})
