% =====================================================================
%  dbfdoc.cls — document class for all DBF team documentation
%  Design language: technical dossier x Swiss restraint.
%  Type: Geist / Geist Mono (OFL).  Colour: monochrome, no signal colour.
%  Engine: XeLaTeX (fontspec / unicode-math). Paper: US Letter, always.
%
%  Options
%    titleblock = dark | light     page-1 masthead (team standard: dark)
%    final                         hide all \dbfnote{} drafting notes
%
%  Before \documentclass, a document sets the path to design-system/:
%    \def\dbfroot{../design-system}
% =====================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{dbfdoc}[2026/10/06 v1.0 DBF team document class]

\RequirePackage{kvoptions}
\SetupKeyvalOptions{family=dbf,prefix=dbf@opt@}
\DeclareStringOption[dark]{titleblock}
\DeclareBoolOption{final}
\ProcessKeyvalOptions*

\LoadClass[10pt,letterpaper,twocolumn]{article}

\providecommand\dbfroot{../design-system}
\def\dbf@fontdir{\dbfroot/fonts/}

% ---------------------------------------------------------------------
%  Page geometry — US Letter, 0.75 in side margins, 0.30 in gutter
% ---------------------------------------------------------------------
\RequirePackage[letterpaper,
  left=0.75in, right=0.75in, top=0.92in, bottom=0.80in,
  columnsep=0.30in, headheight=14pt, headsep=0.20in, footskip=0.34in]{geometry}

% ---------------------------------------------------------------------
%  Colour system — monochrome. Emphasis = weight, ink fills, Bone tint.
% ---------------------------------------------------------------------
\RequirePackage[table]{xcolor}
\definecolor{dbfInk}{HTML}{0B0C0E}
\definecolor{dbfGraphite}{HTML}{2B2E33}
\definecolor{dbfSteel}{HTML}{5B616B}
\definecolor{dbfFog}{HTML}{A9AEB6}
\definecolor{dbfMist}{HTML}{E4E6E9}
\definecolor{dbfBone}{HTML}{F3F2EE}
% Semantic roles (change here only): "selected" marks and their tint
\colorlet{dbfAccent}{dbfInk}
\colorlet{dbfAccentTint}{dbfBone}
\renewcommand\normalcolor{\color{dbfInk}}
\AtBeginDocument{\color{dbfInk}}

% ---------------------------------------------------------------------
%  Type — open-licensed families stored in design-system/fonts
% ---------------------------------------------------------------------
\RequirePackage{fontspec}
\RequirePackage[warnings-off={mathtools-colon,mathtools-overbracket}]{unicode-math}
\defaultfontfeatures{Ligatures=TeX}

% Body and UI share Geist; data, labels and indices use Geist Mono.
% Geist figures are proportional in running text and tabular
% (Numbers=Monospaced) in tables and readouts.
\def\dbf@bodydir{Geist}\def\dbf@bodypre{Geist}
\def\dbf@uidir{Geist}\def\dbf@uipre{Geist}
\def\dbf@monodir{GeistMono}\def\dbf@monopre{GeistMono}
\def\dbf@numfeat{Numbers=Monospaced}

\setmainfont{\dbf@bodypre}[Path=\dbf@fontdir\dbf@bodydir/, Extension=.ttf,
  UprightFont=*-Regular, ItalicFont=*-Italic,
  BoldFont=*-SemiBold, BoldItalicFont=*-SemiBoldItalic,
  FontFace={mb}{n}{*-Medium}, FontFace={mb}{it}{*-MediumItalic}]
\setsansfont{\dbf@uipre}[Path=\dbf@fontdir\dbf@uidir/, Extension=.ttf,
  UprightFont=*-Regular, ItalicFont=*-Italic,
  BoldFont=*-SemiBold, BoldItalicFont=*-SemiBoldItalic,
  FontFace={mb}{n}{*-Medium}]
\setmonofont{\dbf@monopre}[Path=\dbf@fontdir\dbf@monodir/, Extension=.ttf,
  UprightFont=*-Regular, ItalicFont=*-Italic,
  BoldFont=*-SemiBold, BoldItalicFont=*-SemiBold]
% Tracked capitals (labels, running heads), tabular figures, display face
\newfontfamily\dbf@trackedsans{\dbf@uipre}[Path=\dbf@fontdir\dbf@uidir/,
  Extension=.ttf, UprightFont=*-Medium, BoldFont=*-SemiBold, LetterSpace=9]
\newfontfamily\dbf@trackedmono{\dbf@monopre}[Path=\dbf@fontdir\dbf@monodir/,
  Extension=.ttf, UprightFont=*-Regular, BoldFont=*-Medium, LetterSpace=4]
\newfontfamily\dbf@tablefont{\dbf@uipre}[Path=\dbf@fontdir\dbf@uidir/,
  Extension=.ttf, UprightFont=*-Regular, ItalicFont=*-Italic,
  BoldFont=*-SemiBold, \dbf@numfeat]
\newfontfamily\dbf@display{\dbf@uipre}[Path=\dbf@fontdir\dbf@uidir/,
  Extension=.ttf, UprightFont=*-Medium, BoldFont=*-SemiBold, LetterSpace=-1.2]

% Mathematics: IBM Plex Math for operators; letters/digits from the body face
\setmathfont{IBMPlexMath-Regular.ttf}[Path=\dbf@fontdir IBMPlexMath/]
\setmathfont{\dbf@bodypre-Italic.ttf}[Path=\dbf@fontdir\dbf@bodydir/, range=it/{latin,Latin}]
\setmathfont{\dbf@bodypre-Regular.ttf}[Path=\dbf@fontdir\dbf@bodydir/, range=up/{latin,Latin,num}]

\newcommand\dbfmono{\ttfamily}
\newcommand\dbflabelfont{\dbf@trackedmono}
\newcommand\dbfcapsfont{\dbf@trackedsans}
\newcommand\dbftablefont{\dbf@tablefont}

% ---------------------------------------------------------------------
%  Sizes — body 10 pt on a 17.25 pt baseline (= "1.5 lines" for 10 pt)
% ---------------------------------------------------------------------
\renewcommand\normalsize{%
  \@setfontsize\normalsize{10}{17.25}%
  \abovedisplayskip 6pt plus 2pt minus 2pt
  \belowdisplayskip \abovedisplayskip
  \abovedisplayshortskip 2pt plus 2pt
  \belowdisplayshortskip 4pt plus 2pt minus 2pt
  \let\@listi\@listI}
\renewcommand\small{\@setfontsize\small{9}{11.6}}
\renewcommand\footnotesize{\@setfontsize\footnotesize{8}{10}}
\renewcommand\scriptsize{\@setfontsize\scriptsize{7}{8.6}}
\renewcommand\tiny{\@setfontsize\tiny{6.5}{8}}
\normalsize

\setlength\parindent{1.15em}
\setlength\parskip{0pt}
\RequirePackage[protrusion=true]{microtype}
\tolerance=1400 \emergencystretch=1.6em \hbadness=2000
\clubpenalty=4000 \widowpenalty=4000 \displaywidowpenalty=3000
\brokenpenalty=2000

% ---------------------------------------------------------------------
%  Headings — 1.0 / 1.1 / 1.1.1 numbering; mono index, tracked capitals
% ---------------------------------------------------------------------
\RequirePackage{titlesec}
\renewcommand\thesection{\arabic{section}.0}
\renewcommand\thesubsection{\arabic{section}.\arabic{subsection}}
\renewcommand\thesubsubsection{\thesubsection.\arabic{subsubsection}}

\newcommand\dbf@index[1]{\makebox[2.55em][l]{\dbfmono\mdseries\color{dbfSteel}#1}}
\newcommand\dbf@hone[1]{\dbf@secanchor{\dbf@trackedsans\bfseries\MakeUppercase{#1}}}

% Sequence guard: page positions of every section heading and every caption
% are written to the .aux file; tools/check_order.py then verifies that each
% float appears inside its own section (rules: out-of-sequence = missing).
\RequirePackage{zref-savepos,zref-abspage}
\zref@addprop{savepos}{abspage}
\newcounter{dbfflt}
\newcommand\dbf@secanchor{%
  \edef\dbf@tmpname{dbf-sec-\arabic{section}}\expandafter\zsavepos\expandafter{\dbf@tmpname}}
\newcommand\dbf@fltanchor{%
  \stepcounter{dbfflt}%
  \edef\dbf@tmpname{dbf-flt-\arabic{dbfflt}-s\arabic{section}-\@captype-\csname the\@captype\endcsname}%
  \expandafter\zsavepos\expandafter{\dbf@tmpname}}

\titleformat{\section}[block]
  {\color{dbfInk}{\color{dbfInk}\titlerule[0.75pt]}\vspace{3.6pt}%
   \sffamily\fontsize{10.5}{13}\selectfont}
  {\dbf@index{\thesection}}{0pt}{\dbf@hone}
\titlespacing*{\section}{0pt}{12pt plus 3pt minus 2pt}{5pt plus 1pt}

\titleformat{\subsection}[block]
  {\color{dbfInk}\sffamily\bfseries\fontsize{10}{13}\selectfont}
  {\dbf@index{\thesubsection}}{0pt}{}
\titlespacing*{\subsection}{0pt}{8pt plus 2pt minus 1pt}{2pt plus 1pt}

\titleformat{\subsubsection}[runin]
  {\color{dbfInk}\sffamily\bfseries\normalsize}
  {{\dbfmono\mdseries\color{dbfSteel}\thesubsubsection}\enspace}{0pt}{}[\enspace]
\titlespacing*{\subsubsection}{0pt}{5pt plus 1pt}{0pt}

% ---------------------------------------------------------------------
%  Lists — square markers, compact
% ---------------------------------------------------------------------
\RequirePackage{enumitem}
\setlist{nosep, leftmargin=1.15em}
\setlist[itemize]{label={\color{dbfSteel}\rule[0.28ex]{0.36em}{0.36em}}}
\setlist[enumerate]{label={\dbfmono\color{dbfSteel}\arabic*}, leftmargin=1.4em}

% ---------------------------------------------------------------------
%  Floats and captions — FIG. 04 / TABLE 03 in mono, takeaway caption
% ---------------------------------------------------------------------
\RequirePackage{graphicx}
\RequirePackage{stfloats}
\RequirePackage{caption}
\renewcommand\thefigure{\two@digits{\c@figure}}
\renewcommand\thetable{\two@digits{\c@table}}
\DeclareCaptionLabelFormat{dbf}{{\dbf@trackedmono\fontsize{7}{9}\selectfont
  \color{dbfSteel}\MakeUppercase{#1}~#2}}
\DeclareCaptionLabelSeparator{dbf}{\hspace{0.7em}}
\DeclareCaptionFormat{dbf}{\dbf@fltanchor#1#2#3\par}
\captionsetup{format=dbf, font={small,sf}, labelformat=dbf, labelsep=dbf,
  justification=raggedright, singlelinecheck=false, skip=5pt}
\captionsetup[figure]{name=Fig.}
\captionsetup[table]{name=Table, position=top, skip=4pt}

\setcounter{topnumber}{3}\setcounter{bottomnumber}{2}\setcounter{totalnumber}{5}
\setcounter{dbltopnumber}{2}
\renewcommand\topfraction{0.88}\renewcommand\bottomfraction{0.6}
\renewcommand\textfraction{0.08}\renewcommand\floatpagefraction{0.82}
\renewcommand\dbltopfraction{0.88}\renewcommand\dblfloatpagefraction{0.82}
\setlength\floatsep{9pt plus 2pt minus 2pt}
\setlength\textfloatsep{11pt plus 2pt minus 3pt}
\setlength\intextsep{9pt plus 2pt minus 2pt}
\setlength\dblfloatsep{9pt plus 2pt minus 2pt}
\setlength\dbltextfloatsep{12pt plus 2pt minus 3pt}

% ---------------------------------------------------------------------
%  Tables — hairline rules, Mist header, tracked-caps header labels
% ---------------------------------------------------------------------
\RequirePackage{tabularray}
\newcommand\dbf@thead{\dbf@trackedsans\bfseries\fontsize{6.8}{8.5}\selectfont}
\NewTblrEnviron{dbftable}
\SetTblrInner[dbftable]{
  rowsep=2.3pt, colsep=4pt, stretch=0,
  cells={font=\dbf@tablefont\small},
  row{1}={bg=dbfMist, fg=dbfGraphite, font=\dbf@thead, cmd=\MakeUppercase, abovesep=3.2pt, belowsep=2.8pt},
  hline{1}={0.8pt,dbfInk}, hline{2}={0.4pt,dbfGraphite}, hline{Z}={0.8pt,dbfInk},
  hline{3-Y}={0.3pt,dbfMist},
}
% Long variant for one-column pages: same look, breaks across pages and
% repeats the header row. It prints no caption of its own: put
% \captionof{table}{...}\nopagebreak directly above it.
\NewTblrTheme{dbflong}{%
  \DefTblrTemplate{firsthead,middlehead,lasthead}{default}{}%
  \DefTblrTemplate{firstfoot,middlefoot,lastfoot}{default}{}}
\NewTblrEnviron{dbflongtable}
\SetTblrOuter[dbflongtable]{long, theme=dbflong, label=none, entry=none,
  presep=0pt, postsep=6pt}
\SetTblrInner[dbflongtable]{
  rowsep=2.3pt, colsep=4pt, stretch=0, rowhead=1,
  cells={font=\dbf@tablefont\small},
  row{1}={bg=dbfMist, fg=dbfGraphite, font=\dbf@thead, cmd=\MakeUppercase, abovesep=3.2pt, belowsep=2.8pt},
  hline{1}={0.8pt,dbfInk}, hline{2}={0.4pt,dbfGraphite}, hline{Z}={0.8pt,dbfInk},
  hline{3-Y}={0.3pt,dbfMist},
}
% Row style for totals, used in colspecs:  row{Z}={font=\dbftotalrow}
\newcommand\dbftotalrow{\dbf@tablefont\small\bfseries}
% Selected option in a trade table (monochrome system): a Bone-tinted
% column under an inverted ink header tab. In the colspec, write
%   column{4}={bg=dbfAccentTint}, cell{1}{4}={bg=dbfInk, fg=white}
% and wrap the winning score in \dbfselected{...}.
\newcommand\dbfselected[1]{{\bfseries\color{dbfAccent}#1}}

% ---------------------------------------------------------------------
%  Footnotes (citations live here per the proposal rules)
% ---------------------------------------------------------------------
\RequirePackage[hang,flushmargin]{footmisc}
\setlength\footnotemargin{1.1em}
\renewcommand\footnoterule{\kern-3pt{\color{dbfFog}\hrule width 0.22\columnwidth height 0.4pt}\kern 2.6pt}
\setlength{\skip\footins}{10pt plus 3pt minus 2pt}

% ---------------------------------------------------------------------
%  Document metadata
% ---------------------------------------------------------------------
\input{dbf-identity.tex}
\newcommand\dbf@doctitle{Untitled Document}
\newcommand\dbf@doctype{Document}
\newcommand\dbf@docid{AUM-DBF-27-XXX-000}
\newcommand\dbf@rev{A}
\newcommand\dbf@date{\today}
\newcommand\dbfsetdoc[4]{% {title}{type}{doc id}{rev}
  \renewcommand\dbf@doctitle{#1}\renewcommand\dbf@doctype{#2}%
  \renewcommand\dbf@docid{#3}\renewcommand\dbf@rev{#4}}
\newcommand\dbfsetdate[1]{\renewcommand\dbf@date{#1}}
\newcommand\dbfdoctitle{\dbf@doctitle}
\newcommand\dbfdoctype{\dbf@doctype}

% ---------------------------------------------------------------------
%  Running header / footer
% ---------------------------------------------------------------------
\RequirePackage{lastpage}
\RequirePackage{refcount}
\RequirePackage{fancyhdr}
\newcommand\dbf@runhead[1]{{\dbf@trackedsans\fontsize{6.8}{8}\selectfont\color{dbfGraphite}\MakeUppercase{#1}}}
% (footer text is written in capitals directly: \MakeUppercase would also
%  uppercase counter and colour names)
\newcommand\dbf@runfoot[1]{{\dbf@trackedmono\fontsize{6.6}{8}\selectfont\color{dbfSteel}#1}}
\newcommand\dbf@sep{\hspace{0.9em}\NoCaseChange{\textcolor{dbfFog}{/}}\hspace{0.9em}}
\newcommand\dbf@pageof{PAGE \two@digits{\value{page}} / \two@digits{\getpagerefnumber{LastPage}}}
\newcommand\dbf@doccontrol{DOC \dbf@docid\dbf@sep REV \dbf@rev\dbf@sep\MakeUppercase{\dbf@date}}

\fancypagestyle{dbf}{%
  \fancyhf{}%
  \fancyhead[L]{\dbf@runhead{{\bfseries\dbfteamname}\dbf@sep\dbfuniversity}}%
  \fancyhead[R]{\dbf@runhead{\dbfprogram\dbf@sep\dbf@doctype}}%
  \fancyfoot[L]{\dbf@runfoot{\dbf@doccontrol}}%
  \fancyfoot[R]{\dbf@runfoot{\dbf@pageof}}%
  \renewcommand\headrulewidth{0.4pt}%
  \renewcommand\headrule{{\color{dbfFog}\hrule height\headrulewidth width\headwidth}\vskip-\headrulewidth}%
  \renewcommand\footrulewidth{0pt}}
\fancypagestyle{dbffirst}{%
  \fancyhf{}%
  \fancyfoot[L]{\dbf@runfoot{\dbf@doccontrol}}%
  \fancyfoot[R]{\dbf@runfoot{\dbf@pageof}}%
  \renewcommand\headrulewidth{0pt}\renewcommand\footrulewidth{0pt}}
\pagestyle{dbf}

% ---------------------------------------------------------------------
%  Page-1 masthead (absolute positioning on the page background)
% ---------------------------------------------------------------------
% Masthead x positions in inches: left margin, right text edge, text width (a document with other
% side margins redefines all three after \geometry).
\def\dbf@mx{0.75}\def\dbf@mr{7.75}\def\dbf@tw{7}
\newlength\dbf@bandh \setlength\dbf@bandh{1.52in}
\newcommand\dbf@mast@dark{%
  \setlength\unitlength{1in}%
  \put(0,-1.52){\color{dbfInk}\rule{\paperwidth}{1.52in}}%
  \dbf@mast@content{white}{dbfFog}{dbfMist}{dbfGraphite}}
\newcommand\dbf@mast@light{%
  \setlength\unitlength{1in}%
  \put(\dbf@mx,-0.36){\color{dbfInk}\rule{\dbf@tw in}{2.4pt}}%
  \put(\dbf@mx,-1.52){\color{dbfFog}\rule{\dbf@tw in}{0.4pt}}%
  \dbf@mast@content{dbfInk}{dbfSteel}{dbfGraphite}{dbfMist}}
% #1 primary  #2 secondary  #3 university  #4 hairline
\newcommand\dbf@mast@content[4]{%
  \put(\dbf@mx,-0.585){\makebox[0pt][l]{\dbf@trackedsans\bfseries\fontsize{8.6}{10}\selectfont
    \color{#1}\MakeUppercase{\dbfteamname}}}%
  \put(\dbf@mr,-0.585){\makebox[0pt][r]{\dbf@trackedmono\fontsize{6.8}{8}\selectfont
    \color{#2}\MakeUppercase{\dbfprogram\dbf@sep\dbf@doctype}}}%
  \put(\dbf@mx,-0.70){\color{#4}\rule{\dbf@tw in}{0.4pt}}%
  \put(\dbf@mx,-1.07){\makebox[0pt][l]{\dbf@display\fontsize{21}{24}\selectfont\color{#1}\dbf@doctitle}}%
  \put(\dbf@mx,-1.32){\makebox[0pt][l]{\dbf@trackedsans\fontsize{8.4}{10}\selectfont
    \color{#3}\MakeUppercase{\dbfuniversity}}}%
  \put(\dbf@mr,-1.07){\makebox[0pt][r]{\dbf@trackedmono\fontsize{6.6}{8}\selectfont\color{#2}DOC\hspace{0.8em}\dbf@docid}}%
  \put(\dbf@mr,-1.20){\makebox[0pt][r]{\dbf@trackedmono\fontsize{6.6}{8}\selectfont\color{#2}REV \dbf@rev\dbf@sep\MakeUppercase{\dbf@date}}}%
  \put(\dbf@mr,-1.33){\makebox[0pt][r]{\dbf@trackedmono\fontsize{6.6}{8}\selectfont\color{#2}\dbf@pageof}}}

% frontmatter: full-width top matter on page 1 (masthead + summary)
% \dbffrontskip: clear space for the masthead band; a document with a smaller top margin enlarges it.
\newlength\dbffrontskip \setlength\dbffrontskip{0.78in}
\NewDocumentEnvironment{frontmatter}{+b}{%
  \def\dbf@tmp{dark}%
  \ifx\dbf@opt@titleblock\dbf@tmp
    \AddToHookNext{shipout/background}{\dbf@mast@dark}%
  \else
    \AddToHookNext{shipout/background}{\dbf@mast@light}%
  \fi
  \twocolumn[{\thispagestyle{dbffirst}\vspace*{\dbffrontskip}#1\vspace{15pt}}]%
}{}

% ---------------------------------------------------------------------
%  Components
% ---------------------------------------------------------------------
\RequirePackage{tikz}
\newsavebox\dbf@box
% Panel ("Design at a Glance"): bone field, label line, no borders/radii
\NewDocumentEnvironment{dbfpanel}{O{Design at a Glance}}{%
  \setlength\fboxsep{7pt}%
  \begin{lrbox}{\dbf@box}\begin{minipage}[t]{\dimexpr\linewidth-2\fboxsep\relax}%
  \raggedright\sffamily
  {\dbf@trackedmono\fontsize{6.6}{8}\selectfont\color{dbfSteel}\MakeUppercase{#1}}\par
  \vspace{3pt}{\color{dbfFog}\hrule height 0.4pt}\vspace{5pt}}%
  {\end{minipage}\end{lrbox}%
  \colorbox{dbfBone}{\usebox{\dbf@box}}}
% Ink panel (added 31 Oct 2026 for the proposal): the same panel on an Ink
% field, for the page-1 "Design at a Glance" plate. Readouts inside it switch
% to light type automatically.
\NewDocumentEnvironment{dbfinkpanel}{O{Design at a Glance}}{%
  \setlength\fboxsep{8pt}%
  \begin{lrbox}{\dbf@box}\begin{minipage}[t]{\dimexpr\linewidth-2\fboxsep\relax}%
  \def\dbf@rdlab{dbfFog}\def\dbf@rdval{white}\def\dbf@rdunit{dbfFog}%
  \raggedright\sffamily\color{dbfMist}%
  {\dbf@trackedmono\fontsize{6.6}{8}\selectfont\color{dbfFog}\MakeUppercase{#1}}\par
  \vspace{3pt}{\color{dbfGraphite}\hrule height 0.4pt}\vspace{6pt}}%
  {\end{minipage}\end{lrbox}%
  \colorbox{dbfInk}{\usebox{\dbf@box}}}
% Plate: an Ink field holding a dark figure, with a mono label line and an
% optional right-hand note.  \begin{dbfplate}{LABEL}{NOTE} ... \end{dbfplate}
\NewDocumentEnvironment{dbfplate}{mm}{%
  \setlength\fboxsep{0pt}%
  \begin{lrbox}{\dbf@box}\begin{minipage}[t]{\linewidth}%
  \vspace{6pt}\hspace*{7pt}{\dbf@trackedmono\fontsize{6.4}{8}\selectfont\color{dbfFog}\MakeUppercase{#1}}%
  \hfill{\dbf@trackedmono\fontsize{6.4}{8}\selectfont\color{dbfSteel}\MakeUppercase{#2}}\hspace*{7pt}\par
  \vspace{4pt}{\color{dbfGraphite}\hrule height 0.4pt}\vspace{2pt}\centering}%
  {\par\vspace{3pt}\end{minipage}\end{lrbox}%
  \colorbox{dbfInk}{\usebox{\dbf@box}}}
% Instrument-style readout:  \dbfreadout{label}{value}{unit}
\def\dbf@rdlab{dbfSteel}\def\dbf@rdval{dbfInk}\def\dbf@rdunit{dbfSteel}
\newcommand\dbfreadout[3]{%
  \parbox[t]{0.485\linewidth}{\raggedright
    {\dbf@trackedmono\fontsize{6.2}{7.6}\selectfont\color{\dbf@rdlab}\MakeUppercase{#1}}\par
    \vspace{1.5pt}{\dbf@tablefont\bfseries\fontsize{12.5}{14.5}\selectfont\color{\dbf@rdval}#2}%
    \hspace{0.25em}{\sffamily\fontsize{7.6}{9}\selectfont\color{\dbf@rdunit}#3}}}
% Vertical rhythm between readout rows
\newcommand\dbfreadoutgap{\par\vspace{9pt}}
% Figure placeholder:  \dbfplaceholder{width}{height}{label}
\newcommand\dbfplaceholder[3]{%
  \begin{tikzpicture}
    \fill[white] (0,0) rectangle (#1,#2);
    \draw[dbfMist, line width=0.4pt] (0,0) -- (#1,#2) (0,#2) -- (#1,0);
    \draw[dbfFog, line width=0.4pt] (0,0) rectangle (#1,#2);
    \node[fill=white, inner sep=2.5pt, font=\dbf@trackedmono\fontsize{6.4}{8}\selectfont,
          text=dbfSteel] at (#1/2,#2/2) {\MakeUppercase{#3}};
  \end{tikzpicture}}

% Drafting notes: shown in drafts, removed entirely by the `final` option
\ifdbf@opt@final
  \newcommand\dbfnote[1]{\ignorespaces}
\else
  \newcommand\dbfnote[1]{\par\vspace{2pt}{\noindent\sffamily\small\color{dbfSteel}%
    {\dbf@trackedmono\fontsize{6.4}{8}\selectfont NOTE}\enspace\itshape #1\par}\vspace{2pt}}
\fi
% Placeholder prose: about N words of Fog-grey copy, for proving page budgets
\ExplSyntaxOn
\NewDocumentCommand\dbffill{m}{%
  {\color{dbfFog}\prg_replicate:nn{\int_div_round:nn{#1}{10}}
    {Placeholder~copy~sized~to~this~section's~word~budget~for~layout.~}}%
  \ClassWarningNoLine{dbfdoc}{Unfinished value [placeholder~prose] (\string\dbffill)}\unskip}
\ExplSyntaxOff
% Unfinished value: visible mono tag; warns at build time (grep for it)
\NewDocumentCommand\dbftbd{m}{{\dbf@trackedmono\fontsize{7.4}{9}\selectfont\color{dbfSteel}[#1]}%
  \ClassWarningNoLine{dbfdoc}{Unfinished value [\detokenize{#1}] (\string\dbftbd)}}

% ---------------------------------------------------------------------
%  Units and numbers (US units, per contest rules)
% ---------------------------------------------------------------------
\RequirePackage{siunitx}
\sisetup{mode=match, propagate-math-font=true, reset-math-version=false,
  reset-text-family=false, reset-text-series=false, reset-text-shape=false,
  text-family-to-math=true, group-minimum-digits=4,
  per-mode=symbol, inter-unit-product=\ensuremath{\cdot}}
\DeclareSIUnit\foot{ft}
\DeclareSIUnit\inch{in}
\DeclareSIUnit\pound{lb}
\DeclareSIUnit\ounce{oz}
\DeclareSIUnit\mph{mph}
\DeclareSIUnit\knot{kn}

% ---------------------------------------------------------------------
%  PDF metadata and links (quiet: no coloured boxes)
% ---------------------------------------------------------------------
\RequirePackage{hyperref}
\hypersetup{hidelinks, pdfdisplaydoctitle=true, pdfcreator={dbfdoc.cls / XeLaTeX}}
\AtBeginDocument{\hypersetup{pdftitle={\dbf@doctitle\space-- \dbf@doctype},
  pdfauthor={\dbfuniversity}, pdfsubject={\dbfprogram}}}

\endinput
