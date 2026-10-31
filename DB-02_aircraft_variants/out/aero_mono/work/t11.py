import sys,math,json; sys.dont_write_bytecode=True
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src")
from aero_mono import model as M
# S-sweep CLmax table for options
for S in (0.8,0.9,1.0,1.1,1.2,1.3):
    row=[]
    for name,fl in (("plain",dict(type="plain",chord_frac=0.25,defl_land_deg=30)),("plain40",dict(type="plain",chord_frac=0.25,defl_land_deg=40)),("slot",dict(type="slotted",chord_frac=0.30,defl_land_deg=30)),("fowler",dict(type="fowler",chord_frac=0.30,defl_land_deg=35))):
        for eta in (0.5,0.7):
            r=M.aero({"S":S,"flap":dict(fl,span_frac=eta,defl_turn_deg=0)})
            row.append((name,eta,round(r['clmax_landing'],2),[round(x,2) for x in r['ranges']['clmax_landing']],round(r['clmax_landing_untrimmed'],2)))
    print(S,row)
# turn flap
for dt in (5,10,15):
    r=M.aero({"S":0.9,"flap":dict(type="plain",span_frac=0.6,chord_frac=0.25,defl_land_deg=30,defl_turn_deg=dt)})
    print(dt,r['clmax_turn_avail'],r['ranges']['clmax_turn_avail'],r['e_turn_flap'],r['e'])
# RQ4 cross check
r=M.aero({"S":0.232,"span":1.82,"taper":0.78,"fuselage":dict(l=0.843,w=0.198,h=0.15),"nacelle":dict(l=0.272,w=0.18,h=0.174),"V":26.5,"tail":dict(Sh=0.0,Sv=0.0)})
print(r['cd0_parts'],r['cd0_parts']['body']*0.232, r['cd0_parts']['tail']*0.232)
