"""S12 integration and design-space search (DB-02).

Modules (import-safe; no file I/O on import except reading the analysis inputs that
s4_sizing / s6_studies themselves read):

    adapter   Design -> DB-01 pipeline (s4_sizing / s6_studies), overrides from other streams
    physics   batch M2/M3 physics with operating-point detail, margins and binding constraints
    models    resolver: real stream models from W/src/<stream>/model.py, else the S12 stubs
    stubs     clearly marked stand-ins for S2/S3/S4/S6/S7/S8 until their models land
    timing    decision timing: freeze-now, tech-timed (no peeking) and oracle policies
    scoring   completion sampling, field draws, P(1st)
    search    staged search harness (stage 1 screen, stage 2 CRN draws, stage 3 field draws)
    select    pre-registered gates and the variant A/B selection rule (brief Sec. 9)
    report    CSV, JSON and figures into W/out/integration
"""
