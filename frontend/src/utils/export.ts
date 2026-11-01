import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import * as XLSX from "xlsx";

export function exportToPDF(title: string, columns: string[], rows: any[][]) {
  const doc = new jsPDF();
  doc.text(title, 14, 15);
  autoTable(doc, {
    head: [columns],
    body: rows,
    startY: 20,
    theme: "grid",
    styles: { fontSize: 10, cellPadding: 3 },
    headStyles: { fillColor: [2, 132, 199] }, // Sky 600
  });
  doc.save(`${title.replace(/\s+/g, "_")}.pdf`);
}

export function exportToExcel(title: string, columns: string[], rows: any[][]) {
  const wsData = [columns, ...rows];
  const ws = XLSX.utils.aoa_to_sheet(wsData);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Report");
  XLSX.writeFile(wb, `${title.replace(/\s+/g, "_")}.xlsx`);
}