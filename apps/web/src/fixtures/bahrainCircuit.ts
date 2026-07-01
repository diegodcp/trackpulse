export const bahrainCircuit = {
  circuitKey: 'bahrain-2023-stylized',
  circuitName: 'Bahrain International Circuit (Stylized)',
  version: '1.0.0',
  coordinateSystem: 'stylized-svg',
  precisionNote: 'Stylized and approximate track geometry. Not a racing-line map.',
  width: 1200,
  height: 700,
  centerline: [
    { x: 170, y: 380 },
    { x: 210, y: 500 },
    { x: 350, y: 590 },
    { x: 570, y: 600 },
    { x: 850, y: 560 },
    { x: 1020, y: 500 },
    { x: 1075, y: 420 },
    { x: 1050, y: 330 },
    { x: 940, y: 250 },
    { x: 760, y: 205 },
    { x: 520, y: 175 },
    { x: 325, y: 205 },
    { x: 205, y: 285 },
    { x: 170, y: 380 }
  ],
  segments: [
    {
      segmentId: 'bh-s01',
      order: 1,
      label: 'Start/Finish Straight',
      sector: 1,
      cornerId: null,
      type: 'straight',
      path: [
        { x: 170, y: 380 },
        { x: 210, y: 500 }
      ],
      sStartPct: 0,
      sEndPct: 6,
      dominantDirectionDeg: 162
    },
    {
      segmentId: 'bh-s02',
      order: 2,
      label: 'T1 Braking Zone',
      sector: 1,
      cornerId: 'T1',
      type: 'braking',
      path: [
        { x: 210, y: 500 },
        { x: 280, y: 560 }
      ],
      sStartPct: 6,
      sEndPct: 11,
      dominantDirectionDeg: 130
    },
    {
      segmentId: 'bh-s03',
      order: 3,
      label: 'T1 Exit',
      sector: 1,
      cornerId: 'T1',
      type: 'traction_exit',
      path: [
        { x: 280, y: 560 },
        { x: 350, y: 590 }
      ],
      sStartPct: 11,
      sEndPct: 15,
      dominantDirectionDeg: 112
    },
    {
      segmentId: 'bh-s04',
      order: 4,
      label: 'T2-T3 Sweep',
      sector: 1,
      cornerId: 'T2/T3',
      type: 'fast_corner',
      path: [
        { x: 350, y: 590 },
        { x: 470, y: 605 },
        { x: 570, y: 600 }
      ],
      sStartPct: 15,
      sEndPct: 22,
      dominantDirectionDeg: 88
    },
    {
      segmentId: 'bh-s05',
      order: 5,
      label: 'T4 Approach',
      sector: 1,
      cornerId: 'T4',
      type: 'braking',
      path: [
        { x: 570, y: 600 },
        { x: 680, y: 590 }
      ],
      sStartPct: 22,
      sEndPct: 27,
      dominantDirectionDeg: 84
    },
    {
      segmentId: 'bh-s06',
      order: 6,
      label: 'T4 Exit Straight',
      sector: 1,
      cornerId: 'T4',
      type: 'traction_exit',
      path: [
        { x: 680, y: 590 },
        { x: 850, y: 560 }
      ],
      sStartPct: 27,
      sEndPct: 35,
      dominantDirectionDeg: 80
    },
    {
      segmentId: 'bh-s07',
      order: 7,
      label: 'S2 Back Straight',
      sector: 2,
      cornerId: null,
      type: 'straight',
      path: [
        { x: 850, y: 560 },
        { x: 1020, y: 500 }
      ],
      sStartPct: 35,
      sEndPct: 43,
      dominantDirectionDeg: 71
    },
    {
      segmentId: 'bh-s08',
      order: 8,
      label: 'T8 Braking',
      sector: 2,
      cornerId: 'T8',
      type: 'braking',
      path: [
        { x: 1020, y: 500 },
        { x: 1075, y: 420 }
      ],
      sStartPct: 43,
      sEndPct: 49,
      dominantDirectionDeg: 35
    },
    {
      segmentId: 'bh-s09',
      order: 9,
      label: 'T9 Apex',
      sector: 2,
      cornerId: 'T9',
      type: 'slow_corner',
      path: [
        { x: 1075, y: 420 },
        { x: 1050, y: 330 }
      ],
      sStartPct: 49,
      sEndPct: 55,
      dominantDirectionDeg: 344
    },
    {
      segmentId: 'bh-s10',
      order: 10,
      label: 'T10 Exit',
      sector: 2,
      cornerId: 'T10',
      type: 'traction_exit',
      path: [
        { x: 1050, y: 330 },
        { x: 940, y: 250 }
      ],
      sStartPct: 55,
      sEndPct: 63,
      dominantDirectionDeg: 306
    },
    {
      segmentId: 'bh-s11',
      order: 11,
      label: 'T11 Kink',
      sector: 2,
      cornerId: 'T11',
      type: 'medium_corner',
      path: [
        { x: 940, y: 250 },
        { x: 840, y: 220 }
      ],
      sStartPct: 63,
      sEndPct: 68,
      dominantDirectionDeg: 286
    },
    {
      segmentId: 'bh-s12',
      order: 12,
      label: 'T12 Bend',
      sector: 3,
      cornerId: 'T12',
      type: 'fast_corner',
      path: [
        { x: 840, y: 220 },
        { x: 760, y: 205 }
      ],
      sStartPct: 68,
      sEndPct: 72,
      dominantDirectionDeg: 281
    },
    {
      segmentId: 'bh-s13',
      order: 13,
      label: 'T13-T14 Arc',
      sector: 3,
      cornerId: 'T13/T14',
      type: 'medium_corner',
      path: [
        { x: 760, y: 205 },
        { x: 640, y: 190 },
        { x: 520, y: 175 }
      ],
      sStartPct: 72,
      sEndPct: 81,
      dominantDirectionDeg: 277
    },
    {
      segmentId: 'bh-s14',
      order: 14,
      label: 'T15 Final Braking',
      sector: 3,
      cornerId: 'T15',
      type: 'braking',
      path: [
        { x: 520, y: 175 },
        { x: 325, y: 205 }
      ],
      sStartPct: 81,
      sEndPct: 90,
      dominantDirectionDeg: 261
    },
    {
      segmentId: 'bh-s15',
      order: 15,
      label: 'Final Sector Link',
      sector: 3,
      cornerId: null,
      type: 'straight',
      path: [
        { x: 325, y: 205 },
        { x: 205, y: 285 }
      ],
      sStartPct: 90,
      sEndPct: 96,
      dominantDirectionDeg: 236
    },
    {
      segmentId: 'bh-s16',
      order: 16,
      label: 'Last Exit to Line',
      sector: 3,
      cornerId: null,
      type: 'traction_exit',
      path: [
        { x: 205, y: 285 },
        { x: 170, y: 380 }
      ],
      sStartPct: 96,
      sEndPct: 100,
      dominantDirectionDeg: 200
    }
  ]
};

export default bahrainCircuit;
