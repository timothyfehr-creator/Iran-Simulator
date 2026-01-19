// Iran Province Map Data
// Coordinates are relative positions for SVG rendering (0-100 scale)

export interface ProvinceData {
  id: string;
  name: string;
  center: { x: number; y: number };
  population: number; // millions
  ethnicity: 'Persian' | 'Kurdish' | 'Azeri' | 'Baloch' | 'Arab' | 'Lur' | 'Turkmen' | 'Mixed';
  protestStatus: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE';
  strategicFeatures: string;
  borders: string[];
  cities: string[];
}

export const iranProvinces: ProvinceData[] = [
  // Core Persian Regions
  {
    id: 'tehran',
    name: 'Tehran',
    center: { x: 53, y: 34 },
    population: 14.0,
    ethnicity: 'Persian',
    protestStatus: 'HIGH',
    strategicFeatures: 'Capital, government center, IRGC HQ',
    borders: [],
    cities: ['Tehran', 'Karaj', 'Varamin'],
  },
  {
    id: 'isfahan',
    name: 'Isfahan',
    center: { x: 54, y: 50 },
    population: 5.2,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Industrial center, nuclear facilities',
    borders: [],
    cities: ['Isfahan', 'Najafabad', 'Khomeinishahr'],
  },
  {
    id: 'fars',
    name: 'Fars',
    center: { x: 52, y: 62 },
    population: 4.9,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Historical capital (Shiraz)',
    borders: [],
    cities: ['Shiraz', 'Marvdasht', 'Kazerun'],
  },
  {
    id: 'khorasan_razavi',
    name: 'Khorasan Razavi',
    center: { x: 78, y: 32 },
    population: 6.4,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Mashhad shrine, Afghan border',
    borders: ['Afghanistan'],
    cities: ['Mashhad', 'Neyshabur', 'Sabzevar'],
  },

  // Kurdish Regions - High Protest Activity
  {
    id: 'kermanshah',
    name: 'Kermanshah',
    center: { x: 32, y: 40 },
    population: 2.0,
    ethnicity: 'Kurdish',
    protestStatus: 'HIGH',
    strategicFeatures: 'Kurdish heartland, Iraq border',
    borders: ['Iraq'],
    cities: ['Kermanshah', 'Islamabad-e Gharb'],
  },
  {
    id: 'kurdistan',
    name: 'Kurdistan',
    center: { x: 28, y: 32 },
    population: 1.6,
    ethnicity: 'Kurdish',
    protestStatus: 'HIGH',
    strategicFeatures: 'Kurdish region, KDPI activity',
    borders: ['Iraq'],
    cities: ['Sanandaj', 'Marivan', 'Baneh'],
  },
  {
    id: 'west_azerbaijan',
    name: 'West Azerbaijan',
    center: { x: 25, y: 22 },
    population: 3.3,
    ethnicity: 'Kurdish',
    protestStatus: 'HIGH',
    strategicFeatures: 'Turkey/Iraq border, mixed Kurdish-Azeri',
    borders: ['Turkey', 'Iraq'],
    cities: ['Urmia', 'Khoy', 'Mahabad'],
  },

  // Azeri Regions
  {
    id: 'east_azerbaijan',
    name: 'East Azerbaijan',
    center: { x: 35, y: 18 },
    population: 3.9,
    ethnicity: 'Azeri',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Azerbaijan border, Tabriz industrial hub',
    borders: ['Azerbaijan', 'Armenia'],
    cities: ['Tabriz', 'Maragheh', 'Marand'],
  },
  {
    id: 'ardabil',
    name: 'Ardabil',
    center: { x: 40, y: 15 },
    population: 1.3,
    ethnicity: 'Azeri',
    protestStatus: 'LOW',
    strategicFeatures: 'Caspian region, Azerbaijan border',
    borders: ['Azerbaijan'],
    cities: ['Ardabil', 'Meshginshahr'],
  },
  {
    id: 'zanjan',
    name: 'Zanjan',
    center: { x: 40, y: 26 },
    population: 1.1,
    ethnicity: 'Azeri',
    protestStatus: 'LOW',
    strategicFeatures: 'Central plateau',
    borders: [],
    cities: ['Zanjan', 'Abhar'],
  },

  // Baloch Region - High Tension
  {
    id: 'sistan_baluchestan',
    name: 'Sistan-Baluchestan',
    center: { x: 82, y: 62 },
    population: 2.9,
    ethnicity: 'Baloch',
    protestStatus: 'HIGH',
    strategicFeatures: 'Sunni majority, Pakistan/Afghanistan border, Zahedan massacre site',
    borders: ['Pakistan', 'Afghanistan'],
    cities: ['Zahedan', 'Chabahar', 'Iranshahr'],
  },

  // Arab Regions
  {
    id: 'khuzestan',
    name: 'Khuzestan',
    center: { x: 32, y: 52 },
    population: 4.7,
    ethnicity: 'Arab',
    protestStatus: 'HIGH',
    strategicFeatures: 'Oil fields, Iraq border, Arab minority',
    borders: ['Iraq'],
    cities: ['Ahvaz', 'Abadan', 'Khorramshahr'],
  },

  // Lur Regions
  {
    id: 'lorestan',
    name: 'Lorestan',
    center: { x: 37, y: 46 },
    population: 1.8,
    ethnicity: 'Lur',
    protestStatus: 'HIGH',
    strategicFeatures: 'Zagros mountains, tribal areas',
    borders: [],
    cities: ['Khorramabad', 'Borujerd', 'Dorud'],
  },
  {
    id: 'ilam',
    name: 'Ilam',
    center: { x: 28, y: 45 },
    population: 0.6,
    ethnicity: 'Lur',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Iraq border',
    borders: ['Iraq'],
    cities: ['Ilam', 'Dehloran'],
  },

  // Turkmen Region
  {
    id: 'golestan',
    name: 'Golestan',
    center: { x: 60, y: 20 },
    population: 1.9,
    ethnicity: 'Turkmen',
    protestStatus: 'LOW',
    strategicFeatures: 'Turkmenistan border, Caspian coast',
    borders: ['Turkmenistan'],
    cities: ['Gorgan', 'Gonbad-e Kavus'],
  },

  // Other Key Provinces
  {
    id: 'hormozgan',
    name: 'Hormozgan',
    center: { x: 62, y: 75 },
    population: 1.8,
    ethnicity: 'Mixed',
    protestStatus: 'LOW',
    strategicFeatures: 'Strait of Hormuz, naval bases',
    borders: [],
    cities: ['Bandar Abbas', 'Qeshm'],
  },
  {
    id: 'bushehr',
    name: 'Bushehr',
    center: { x: 45, y: 68 },
    population: 1.2,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Nuclear power plant, Persian Gulf coast',
    borders: [],
    cities: ['Bushehr'],
  },
  {
    id: 'yazd',
    name: 'Yazd',
    center: { x: 60, y: 52 },
    population: 1.1,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Desert region, historic city',
    borders: [],
    cities: ['Yazd'],
  },
  {
    id: 'kerman',
    name: 'Kerman',
    center: { x: 70, y: 58 },
    population: 3.2,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Mining region, desert',
    borders: [],
    cities: ['Kerman', 'Rafsanjan', 'Jiroft'],
  },
  {
    id: 'mazandaran',
    name: 'Mazandaran',
    center: { x: 54, y: 24 },
    population: 3.3,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Caspian coast, popular tourism',
    borders: [],
    cities: ['Sari', 'Babol', 'Amol'],
  },
  {
    id: 'gilan',
    name: 'Gilan',
    center: { x: 42, y: 20 },
    population: 2.5,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Caspian coast, historically restive',
    borders: [],
    cities: ['Rasht', 'Anzali', 'Lahijan'],
  },

  // Additional Provinces
  {
    id: 'qom',
    name: 'Qom',
    center: { x: 52, y: 42 },
    population: 1.3,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Religious center, Shia seminary hub, regime stronghold',
    borders: [],
    cities: ['Qom'],
  },
  {
    id: 'markazi',
    name: 'Markazi',
    center: { x: 47, y: 44 },
    population: 1.4,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Industrial center, Arak nuclear facility',
    borders: [],
    cities: ['Arak', 'Saveh', 'Khomein'],
  },
  {
    id: 'alborz',
    name: 'Alborz',
    center: { x: 49, y: 32 },
    population: 2.7,
    ethnicity: 'Persian',
    protestStatus: 'HIGH',
    strategicFeatures: 'Tehran suburbs, industrial corridor',
    borders: [],
    cities: ['Karaj', 'Fardis', 'Shahriar'],
  },
  {
    id: 'qazvin',
    name: 'Qazvin',
    center: { x: 45, y: 32 },
    population: 1.3,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Historic capital, industrial zone',
    borders: [],
    cities: ['Qazvin', 'Takestan'],
  },
  {
    id: 'hamadan',
    name: 'Hamadan',
    center: { x: 40, y: 38 },
    population: 1.8,
    ethnicity: 'Persian',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Ancient city, agricultural region',
    borders: [],
    cities: ['Hamadan', 'Malayer', 'Nahavand'],
  },
  {
    id: 'chaharmahal',
    name: 'Chaharmahal-Bakhtiari',
    center: { x: 49, y: 55 },
    population: 0.95,
    ethnicity: 'Lur',
    protestStatus: 'MEDIUM',
    strategicFeatures: 'Zagros mountains, Bakhtiari tribal lands',
    borders: [],
    cities: ['Shahrekord', 'Borujen'],
  },
  {
    id: 'kohgiluyeh',
    name: 'Kohgiluyeh-Boyer-Ahmad',
    center: { x: 42, y: 58 },
    population: 0.71,
    ethnicity: 'Lur',
    protestStatus: 'LOW',
    strategicFeatures: 'Zagros mountains, tribal region',
    borders: [],
    cities: ['Yasuj', 'Dehdasht'],
  },
  {
    id: 'semnan',
    name: 'Semnan',
    center: { x: 62, y: 32 },
    population: 0.7,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Desert region, transit corridor to Khorasan',
    borders: [],
    cities: ['Semnan', 'Shahroud', 'Damghan'],
  },
  {
    id: 'north_khorasan',
    name: 'North Khorasan',
    center: { x: 70, y: 24 },
    population: 0.86,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Turkmenistan border, mixed Persian-Turkmen',
    borders: ['Turkmenistan'],
    cities: ['Bojnurd', 'Shirvan'],
  },
  {
    id: 'south_khorasan',
    name: 'South Khorasan',
    center: { x: 76, y: 48 },
    population: 0.77,
    ethnicity: 'Persian',
    protestStatus: 'LOW',
    strategicFeatures: 'Afghanistan border, saffron production',
    borders: ['Afghanistan'],
    cities: ['Birjand', 'Qaen', 'Ferdows'],
  },
];

// Color schemes for different data views
export const ethnicityColors: Record<string, string> = {
  Persian: '#3b82f6',   // Blue
  Kurdish: '#ef4444',   // Red
  Azeri: '#22c55e',     // Green
  Baloch: '#f97316',    // Orange
  Arab: '#eab308',      // Yellow
  Lur: '#8b5cf6',       // Purple
  Turkmen: '#14b8a6',   // Teal
  Mixed: '#6b7280',     // Gray
};

export const protestStatusColors: Record<string, string> = {
  HIGH: '#ef4444',      // Red
  MEDIUM: '#f59e0b',    // Amber
  LOW: '#22c55e',       // Green
  NONE: '#6b7280',      // Gray
};

// Neighboring countries for context
export interface NeighborCountry {
  name: string;
  position: { x: number; y: number };
  labelOffset: { x: number; y: number };
}

export const neighboringCountries: NeighborCountry[] = [
  { name: 'Turkey', position: { x: 15, y: 18 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Iraq', position: { x: 18, y: 45 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Kuwait', position: { x: 25, y: 62 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Saudi Arabia', position: { x: 30, y: 75 }, labelOffset: { x: 0, y: 0 } },
  { name: 'UAE', position: { x: 52, y: 80 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Oman', position: { x: 70, y: 82 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Pakistan', position: { x: 92, y: 58 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Afghanistan', position: { x: 88, y: 35 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Turkmenistan', position: { x: 75, y: 12 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Azerbaijan', position: { x: 38, y: 8 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Armenia', position: { x: 28, y: 10 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Caspian Sea', position: { x: 50, y: 12 }, labelOffset: { x: 0, y: 0 } },
  { name: 'Persian Gulf', position: { x: 42, y: 78 }, labelOffset: { x: 0, y: 0 } },
];
