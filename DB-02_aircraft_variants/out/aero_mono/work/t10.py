import sys,math; sys.dont_write_bytecode=True
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src")
from aero_mono import model as M
r=M.aero({"S":0.9}); print(r['e_parts'],r['ranges']['e'])
r=M.aero({"S":0.9,"winglet":{"h_frac":0.15}}); print(r['e'],r['e_parts'],r['ranges']['e'],r['cd0'],r['root_bending_ratio'],r['mass_delta_kg'])
# AR 5.2 check: S=1.82^2/5.2=0.637 (table clamps S at 0.8 -> e_avl slightly high); report parts
r=M.aero({"S":1.82**2/5.2}); print('AR5.2',r['e_parts'])
