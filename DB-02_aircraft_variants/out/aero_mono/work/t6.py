import sys; sys.dont_write_bytecode=True
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src")
from aero_mono import model as M
import json,time
for f in ("plain","slotted","fowler","none"):
    t=time.time()
    r=M.aero({"S":0.9,"flap":{"type":f,"span_frac":0.6,"chord_frac":0.25 if f=="plain" else 0.30,"defl_land_deg":30,"defl_turn_deg":0}})
    print(f, round(time.time()-t,3), {k:(round(v,4) if isinstance(v,float) else v) for k,v in r.items() if k in("cd0","e","k","clmax_clean","clmax_landing","clmax_landing_untrimmed","clmax_turn_avail","cm0","cm_landing","mass_delta_kg")})
    print('  ',{k:round(v,4) for k,v in r['cd0_parts'].items()}, r['ranges']['clmax_landing'], r['ranges']['e'], r['ranges']['f_body_m2'])
