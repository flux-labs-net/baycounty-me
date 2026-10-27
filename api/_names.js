// Display casing for names that arrive in all caps (Sunbiz, check registers, IRS filings, the elections office).
// The same rules as data/entities/ids.py biz_case and person_case, so a name reads the same in the build, the API and
// the page scripts. api/__tests__/names.test.js checks the two agree on every name in the published entity list.
// Display only: matching keys and stored records keep the name as filed.
// Loaded by the API (require) and bundled into /assets/site.js (window.BCNames, BC.bizCase, BC.personCase, BC.nameCase).
(function (root) {
  const set = s => new Set(s.split(' '));
  const UPPER_KEEP = set('LLC LLP LP PA PLLC PC NA USA US FL II III IV ADP AT&T FPL CSX UPS HVAC AC TV FM AM DBA GIS IT PCB PCBH EMR EMS RV ' +
    'ACH CPA PE DDA PMT ECSC CRI MWB USFA WSL EPCI EJHG FTS NCMC JDF RDK CK JS&S PBS&J YMCA YWCA NAACP AARP PTA PTO VFW CDC CRA FSU UWF ' +
    'GCSC TDC FDOT FEMA HUD');
  const LOWER = set('and of the for in on at to by a an or de');
  const WORDS3 = set('bay sea oak sun pro air one new top ace all big red car art law lab dog day way old gas oil ice tax box van bus cab fix ' +
    'net web map pet eye joe bob tom jim ann sam dan ray lee kim fun hot joy key max mix now own pay run sky tee toy two six ' +
    'ten bar inn spa tan tin mr dr st mt ft go my we me so up oh hi ma');
  const FIXED = {INC: 'Inc', CO: 'Co', CORP: 'Corp', LTD: 'Ltd', MGM: 'Mgmt', MGMT: 'Mgmt', SVCS: 'Svcs', AMEX: 'Amex', VISA: 'Visa',
    MCDONALD: 'McDonald', MCKIM: 'McKim', MCMAHON: 'McMahon'};
  const NAME_UPPER = set('II III IV VI VII VIII MD DDS DMD DVM CPA ESQ PA PE RN USN USAF USMC JD LCSW CFP MBA APRN ARNP CRNA LPN BSN MSN ' +
    'DNP FNP MPH MSW MSA MHA LMHC LMFT AIA CFA CLU CHFC CPCU CCIM GRI PMP SPHR CFRE FACS FACP RPH AICP LEED CGC CBC CPM CMA EA USA USCG');
  const TITLED_CRED = set('MD DDS DMD DVM CPA ESQ APRN ARNP CRNA LCSW LMHC LMFT MBA MPH MSW JD RN');
  const NAME_UPPER_LATE = set('DO OD DC NP MA MS BS PT OT');
  const NAME_FIXED = {JR: 'Jr', SR: 'Sr', PHD: 'PhD', EDD: 'EdD', PSYD: 'PsyD', PHARMD: 'PharmD', DMIN: 'DMin', RET: 'Ret', MR: 'Mr', MRS: 'Mrs', DR: 'Dr'};
  const MAC = set('macdonald macdougall macgregor mackenzie mackinnon mackay maclean macleod macmillan macneil macpherson macarthur ' +
    'macaulay macfarlane macintosh macinnis macrae macqueen maclaren macintyre maclachlan macnamara macdonell maccallum mackintosh macivor');

  const cap = s => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  const replaceAll = (s, a, b) => s.split(a).join(b);
  const isUpper = s => /[A-Za-z]/.test(s) && s === s.toUpperCase();
  const isLower = s => /[A-Za-z]/.test(s) && s === s.toLowerCase();

  function namePiece(p) {
    const lo = p.toLowerCase();
    if (lo.length > 2 && lo.startsWith('mc')) return 'Mc' + cap(lo.slice(2));
    if (MAC.has(lo)) return 'Mac' + cap(lo.slice(3));
    return cap(lo);
  }

  function caseWord(w, first) {
    if (/^[WK][A-Z]{2,3}-(TV|FM|AM),?$/.test(w)) return w;  // call signs: WJHG-TV
    const core = w.replace(/[^A-Za-z&]/g, ''), up = core.toUpperCase();
    if (!core) return w;
    if (up in FIXED) return replaceAll(w, core, FIXED[up]);
    if (/^\d+(ST|ND|RD|TH)(\W*)$/.test(w)) return w.toLowerCase();  // ordinals: 1ST -> 1st
    if (UPPER_KEEP.has(up) || core.includes('&') || /\d/.test(w)) return w;
    if (!first && LOWER.has(core.toLowerCase())) return w.toLowerCase();
    if (core.length <= 3 && !WORDS3.has(core.toLowerCase())) return w;  // short initials: CW, RJ, GAC
    return w.replace(/[A-Za-z]+/g, namePiece).replace(/'S\b/g, "'s");
  }

  /** 'BALDWIN CONTAINER SYSTEMS INC' -> 'Baldwin Container Systems Inc'. Names with lower-case letters are left alone. */
  function bizCase(name) {
    if (typeof name !== 'string' || !name || /[a-z]/.test(name) || !/[A-Z]/.test(name)) return name;
    const words = name.split(' ');
    if (words.length === 1 && name.replace(/[^A-Z]/g, '').length <= 4) return FIXED[name] || name;  // a lone acronym
    return words.map((w, i) => caseWord(w, i === 0)).join(' ');
  }

  function nameWord(w, first, afterComma) {
    const core = w.replace(/[^A-Za-z]/g, ''), up = core.toUpperCase();
    if (!core) return w;
    if (core.length === 1) return w.toUpperCase();  // an initial
    if (NAME_UPPER_LATE.has(up) && afterComma) return w.replace(new RegExp(core, 'gi'), up);
    if (up === 'MS' && first) return replaceAll(w, core, 'Ms');
    if (up in NAME_FIXED) return replaceAll(w, core, NAME_FIXED[up]);
    if (NAME_UPPER.has(up) && !first) return w.replace(new RegExp(core, 'gi'), up);
    return w.replace(/[A-Za-z]+/g, namePiece).replace(/(?<=[a-z])'S\b/g, "'s");
  }

  /** 'JOHN A MCDANIEL III' -> 'John A McDaniel III'. Mixed-case names keep their casing, apart from words in caps and
      the slips a plain title-casing leaves ('Mcdaniel', 'Iii', "O'neal"). */
  function personCase(name) {
    if (typeof name !== 'string' || !/[A-Za-z]/.test(name)) return name;
    let s = name.replace(/\s+/g, ' ').trim();
    const words = s.split(' '), n = words.length;
    const prev = i => words[(i - 1 + n) % n];
    if (isUpper(s) || isLower(s)) return words.map((w, i) => nameWord(w, i === 0, i > 0 && prev(i).endsWith(','))).join(' ');
    s = words.map((w, i) => /[A-Z]{3}/.test(w) ? nameWord(w, i === 0, prev(i).endsWith(',')) : w).join(' ');
    const count = s.split(' ').filter(Boolean).length;
    s = s.replace(/(?<=\S )([A-Z][a-z]{1,4})\b(\.?)$/, (m, a, b) => TITLED_CRED.has(a.toUpperCase()) && count >= 3 ? a.toUpperCase() + b : m);
    s = s.replace(/\bMc([a-z])/g, (m, a) => 'Mc' + a.toUpperCase());
    s = s.replace(/\b(O|D)'([a-z])/g, (m, a, b) => a + "'" + b.toUpperCase());
    return s.replace(/(?<=\s)(Ii|Iii|Iv)\b/g, m => m.toUpperCase());
  }

  // People (officials, candidates, board members, owners) get name casing; everything else business casing.
  const PEOPLE = new Set(['person', 'member', 'owner', 'candidate', 'official']);
  const nameCase = (name, kind) => PEOPLE.has(String(kind || '').split(':')[0]) ? personCase(name) : bizCase(name);

  const api = {bizCase, personCase, nameCase};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.BCNames = api;
})(typeof window !== 'undefined' ? window : this);
