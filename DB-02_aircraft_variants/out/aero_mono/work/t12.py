import sys, json; sys.dont_write_bytecode=True
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src\aero_mono")
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src")
import run_impacts as R
from aero_mono import model as M
out={}
for name,S,u in R.DESIGNS[:2]:
    b=R.base_dict(S); a0=M.aero({"S":S})
    for h in (0.10,0.15):
        a=M.aero({"S":S,"winglet":{"h_frac":h}})
        # x3 bracket: AVL de x3 in e_inv
        import math
        de=a["e_parts"]["e_inv"]-a0["e_parts"]["e_inv"]
        ar=1.82**2/S
        k3=1/(math.pi*ar*(a0["e_parts"]["e_inv"]+3*de)*a["e_parts"]["k_fuse"])+a["e_parts"]["K_visc"]
        e3=1/(math.pi*ar*k3)
        bb=dict(b); bb["e"]=R.RAY(S)*e3/a0["e"]; bb["cd0_parts"]={**b["cd0_parts"],"other":a["cd0"]-a0["cd0"]}; bb["mass_delta_kg"]=a["mass_delta_kg"]
        d=R.A.REF_D01.with_(id="wl3",s=S,unit=u,aero=bb); r=R.A.robust(d,R.Ps)
        base=json.load(open('../impacts.json'))[f"{name}|baseline"]["central"]["mean"]
        out[f"{name}|{h}"]=(round(r["mean"]-base,3), round(e3-a0["e"],3))
        print(name,h,out[f"{name}|{h}"],flush=True)
json.dump(out,open('../winglet_x3.json','w'))
