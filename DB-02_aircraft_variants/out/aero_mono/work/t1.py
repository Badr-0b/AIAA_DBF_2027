import sys; sys.dont_write_bytecode=True
sys.path.insert(0, r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src\aero_mono")
import avl_tools as A
from pathlib import Path
A.WORK.mkdir(parents=True, exist_ok=True)
S,b=0.9,1.82
for taper in (0.5,0.7,1.0):
    p=A.WORK/"m.avl"
    A.write_avl(p,S,b,taper,A._surface_wing("Wing",S,b,taper))
    r=A.run_case(p,4.0)
    print(taper,{k:v for k,v in r.items() if k!='strips'}, 1/(3.14159*b*b/S*r['CDi']/r['CL']**2))
# with body
p=A.WORK/"m2.avl"
body=A._body("fus",1.05,0.22,x0=-0.35,z0=0.0)
A.write_avl(p,S,b,0.7,A._surface_wing("Wing",S,b,0.7),body)
r=A.run_case(p,4.0); print('body',{k:v for k,v in r.items() if k!='strips'})
