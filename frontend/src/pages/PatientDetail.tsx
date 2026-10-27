import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Patient, Paginated } from "../api/types";

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();

  const pharmOrders = useQuery({
    queryKey: ["patient", id, "pharmacy"],
    queryFn: async () => (await api.get<Paginated<any>>(`/pharmacy-orders/?patient=${id}`)).data.results,
    enabled: !!id,
  });

  const { data: p, isLoading } = useQuery({
    queryKey: ["patient", id],
    queryFn: async () => (await api.get<Patient>(`/patients/${id}/`)).data,
    enabled: !!id,
  });

  if (isLoading) return <p className="text-slate-500">Loading…</p>;
  if (!p) return <p className="text-red-600">Patient not found.</p>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link to="/patients" className="text-sm text-sky-700">← Patients</Link>
        <h1 className="text-2xl font-semibold">{p.full_name}</h1>
        <span className="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono">{p.mrn}</span>
        {p.is_minor && <span className="text-xs bg-amber-100 text-amber-700 rounded px-2 py-0.5">Minor</span>}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card title="Identity">
          <Row label="Sex" value={p.sex} />
          <Row label="DOB" value={p.dob || "—"} />
          <Row label="Age" value={p.age !== null ? String(p.age) : "—"} />
          <Row label="National ID (NRC)" value={p.national_id || "—"} />
          <Row label="Passport" value={p.passport_number || "—"} />
          <Row label="NHIMA #" value={p.nhima_number || "—"} />
        </Card>

        <Card title="Contact">
          <Row label="Phone" value={p.phone || "—"} />
          <Row label="Alt Phone" value={p.alternative_phone || "—"} />
          <Row label="Email" value={p.email || "—"} />
        </Card>

        <Card title="Address">
          <Row label="Province" value={p.province || "—"} />
          <Row label="District" value={p.district || "—"} />
          <Row label="City/Town" value={p.city_town || "—"} />
          <Row label="Compound/Village" value={p.compound_village || "—"} />
          <Row label="Street" value={p.street_address || "—"} />
          {p.address && <Row label="Notes" value={p.address} />}
        </Card>

        <Card title="Demographics">
          <Row label="Marital Status" value={p.marital_status || "—"} />
          <Row label="Occupation" value={p.occupation || "—"} />
        </Card>

        {p.is_minor && (
          <Card title="Parent / Guardian" className="md:col-span-2 bg-amber-50/50">
            <Row label="Name" value={p.guardian_name} />
            <Row label="Relationship" value={p.guardian_relationship} />
            <Row label="Phone" value={p.guardian_phone} />
            <Row label="NRC" value={p.guardian_nrc || "—"} />
            <Row label="Address" value={p.guardian_address || "—"} />
          </Card>
        )}

        <Card title="Dispensing History" className="md:col-span-2">
          {!pharmOrders.data || pharmOrders.data.length === 0 ? (
            <p className="text-sm text-slate-500">No medications dispensed for this patient.</p>
          ) : (
            <ul className="divide-y text-sm">
              {pharmOrders.data.map((o: any) => (
                <li key={o.id} className="py-3">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-medium text-slate-700">{o.visit_no}</span>
                    <span className="text-xs text-slate-500">
                      {o.dispensed_at ? new Date(o.dispensed_at).toLocaleDateString() : "Pending"}
                    </span>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {o.items.map((i: any) => (
                      <span key={i.id} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">
                        {i.quantity_dispensed}x {i.medicine_name}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Clinical Snapshot" className="md:col-span-2">
          <Row label="Blood Group" value={p.blood_group || "—"} />
          <Row label="Allergies" value={p.allergies || "None known"} />
          <Row label="Chronic Conditions" value={p.chronic_conditions || "None"} />
        </Card>
      </div>
    </div>
  );
}

function Card({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border rounded-lg p-5 ${className}`}>
      <h2 className="text-sm font-semibold text-slate-800 mb-4 border-b pb-2">{title}</h2>
      <dl className="space-y-2 text-sm">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2 font-medium">{value}</dd>
    </div>
  );
}
