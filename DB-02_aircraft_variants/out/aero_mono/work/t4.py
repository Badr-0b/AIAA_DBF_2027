import json, numpy as np
R=json.load(open('../xfoil_polars.json'))
for r in R:
    rows=np.array(r['rows']); a,cl,cd,cm=rows.T
    m=(cl>=0.0)&(cl<=1.25)
    # fit cd = a0 + kp*cl^2 over 0.3..1.1
    s=(cl>=0.3)&(cl<=1.1)
    A=np.vstack([np.ones(s.sum()),cl[s]**2]).T
    c,res,_,_=np.linalg.lstsq(A,cd[s],rcond=None)
    # also quad with linear term
    A3=np.vstack([np.ones(s.sum()),cl[s],cl[s]**2]).T
    c3=np.linalg.lstsq(A3,cd[s],rcond=None)[0]
    i=np.argmin(cd[(cl>0)]); 
    print(r['airfoil'],int(r['re']),r['ncrit'],'cdmin %.4f at cl %.2f'%(cd[cl>0].min(), cl[cl>0][np.argmin(cd[cl>0])]),'fit a=%.4f kp=%.4f'%tuple(c), 'cd@.35 %.4f @.7 %.4f @1.0 %.4f'%tuple(np.interp([.35,.7,1.0],cl[np.argsort(cl)],cd[np.argsort(cl)])))
