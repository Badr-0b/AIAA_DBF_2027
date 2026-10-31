import sys,tempfile,json,numpy as np
from pathlib import Path
tempfile.tempdir=str(Path('tmp').resolve()); sys.dont_write_bytecode=True
sys.path.insert(0,r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\analysis")
import xfoil_tools as xt
AF=Path(r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\dbf_airfoil_study_handoff\dbf_airfoil_study\airfoils")
out=[]
for nc in (9.0,5.0):
    rows,_=xt.sweep_up(AF/"sd7037.dat",3.0e5,-4.0,18.0,0.5,None,nc)
    cl=np.array([r[1] for r in rows]); cd=np.array([r[2] for r in rows]); o=np.argsort(cl)
    print(nc,'cdmin %.4f'%cd.min(),[round(float(np.interp(x,cl[o],cd[o])),4) for x in (.35,.7,1.0)], 'clmax',xt.clmax(rows)[:2])
    out.append({"airfoil":"sd7037","re":3e5,"ncrit":nc,"rows":rows,"clmax":xt.clmax(rows)[0],"alpha_clmax":xt.clmax(rows)[1],"stall_captured":xt.clmax(rows)[2]})
json.dump(out,open('../xfoil_polars_3e5.json','w'))
