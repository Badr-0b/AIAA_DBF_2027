# External analysis tools

The Windows binaries are not in git (`.gitignore`). Download each from its author's page and check the hash.

| File | Tool | Source | SHA-256 |
|---|---|---|---|
| `xfoil.exe` | XFoil 6.99 (M. Drela, H. Youngren), 2-D panel method with a coupled boundary-layer solver | `XFOIL6.99.zip` from https://web.mit.edu/drela/Public/web/xfoil/ (the same file as the team's airfoil study) | `c17342f84ae260c2b11a74cd0e2fb8189a5f8954c6bb7a8467a0f27055c7faea` |
| `avl352.exe` | AVL 3.52 (M. Drela, H. Youngren, 2 Sep 2025), vortex-lattice method | https://web.mit.edu/drela/Public/web/avl/avl352.exe, downloaded 15 Oct 2026 | `443520d255408491222a8df9060bd000f78da95a68845a2f6efdbc67e203f07a` |
| `avl_doc.txt` | AVL user guide | https://web.mit.edu/drela/Public/web/avl/avl_doc.txt | `1f20742e991665a01318f051d367b83ebdc3bfad9c4048ee9cf0778c4148e1c4` |

Both programs are GPL. Scripts find them through the environment variables `XFOIL_EXE` and `AVL_EXE`, then `PATH`, then this folder.

Neither tool is CFD:
- **XFoil** is 2-D and attached-flow-dominated. It over-predicts maximum lift, badly so with a deflected flap (see `out/clmax_report.txt`).
- **AVL** is inviscid and linear. It gives the span loading; stall is applied afterwards with measured section data (the critical-section method).
