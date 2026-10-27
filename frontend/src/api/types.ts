export interface Patient {
  id: number;
  mrn: string;
  first_name: string;
  last_name: string;
  full_name: string;
  dob: string | null;
  sex: string;
  age: number | null;
  is_minor: boolean;
  national_id: string;
  passport_number: string;
  nhima_number: string;
  phone: string;
  alternative_phone: string;
  email: string;
  address: string;
  province: string;
  district: string;
  city_town: string;
  compound_village: string;
  street_address: string;
  postal_code: string;
  guardian_name: string;
  guardian_relationship: string;
  guardian_phone: string;
  guardian_nrc: string;
  guardian_address: string;
  marital_status: string;
  occupation: string;
  blood_group: string;
  allergies: string;
  chronic_conditions: string;
  created_at: string;
}

export interface Visit {
  id: number;
  visit_no: string;
  patient: number;
  patient_name: string;
  visit_type: string;
  status: string;
  arrived_at: string;
  closed_at: string | null;
  attending_doctor: number | null;
}

export interface Vitals {
  id: number;
  temperature_c: string | null;
  weight_kg: string | null;
  systolic: number | null;
  diastolic: number | null;
  pulse: number | null;
  spo2: number | null;
  recorded_at: string;
}

export interface ClinicalNote {
  id: number;
  kind: string;
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  created_at: string;
}

export interface Order {
  id: number;
  kind: string;
  status: string;
  priority: string;
  notes: string;
  created_at: string;
  items: { id: number; code: string; description: string; quantity: number }[];
}

export interface LabResult {
  id: number;
  value_text: string;
  unit: string;
  flag: string;
  comment: string;
  resulted_at: string;
}

export interface LabOrder {
  id: number;
  test: number;
  test_name: string;
  test_code: string;
  patient_name: string;
  result: LabResult | null;
  status: string;
  ordered_at: string;
}

export interface Timeline {
  id: number;
  visit_no: string;
  visit_type: string;
  status: string;
  arrived_at: string;
  closed_at: string | null;
  patient: Patient;
  vitals: Vitals | null;
  notes: ClinicalNote[];
  orders: Order[];
  lab_orders: LabOrder[];
  rad_orders: unknown[];
  pharm_orders: unknown[];
}

export interface DashboardSummary {
  date: string;
  census: {
    total: number;
    waiting: number;
    triaged: number;
    in_consultation: number;
    closed: number;
  };
  revenue: { today: string; this_month: string };
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
