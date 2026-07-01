"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { supplierService } from "@/services/supplier.service";
import { formatDate } from "@/lib/utils";
import { Plus, Search, Star, MapPin, Mail, Phone, Users } from "lucide-react";
import type { Supplier } from "@/types";

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [form, setForm] = useState({
    name: "", email: "", phone: "", country: "", city: "", address: "", categories: "",
  });

  useEffect(() => { loadSuppliers(); }, []);

  async function loadSuppliers() {
    setLoading(true);
    try {
      const data = await supplierService.list({ limit: 50 });
      setSuppliers(data.items || data as any);
    } catch { }
    setLoading(false);
  }

  function openCreate() {
    setEditingSupplier(null);
    setForm({ name: "", email: "", phone: "", country: "", city: "", address: "", categories: "" });
    setDialogOpen(true);
  }

  function openEdit(s: Supplier) {
    setEditingSupplier(s);
    setForm({
      name: s.name,
      email: s.email,
      phone: s.phone || "",
      country: s.country,
      city: s.city || "",
      address: s.address || "",
      categories: s.categories?.map((c) => c.category_name).join(", ") || "",
    });
    setDialogOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const payload: any = {
      name: form.name,
      email: form.email,
      phone: form.phone || undefined,
      country: form.country,
      city: form.city || undefined,
      address: form.address || undefined,
      categories: form.categories.split(",").map((c) => c.trim()).filter(Boolean),
    };
    try {
      if (editingSupplier) {
        await supplierService.update(editingSupplier.id, payload);
      } else {
        await supplierService.create(payload);
      }
      setDialogOpen(false);
      loadSuppliers();
    } catch (err) { console.error(err); }
  }

  const filtered = suppliers.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.email.toLowerCase().includes(search.toLowerCase()) ||
      s.country.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Suppliers</h1>
          <p className="text-muted-foreground mt-1">Manage your vendor database</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate}>
              <Plus className="w-4 h-4 mr-2" /> Add Supplier
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{editingSupplier ? "Edit Supplier" : "Add New Supplier"}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSave} className="space-y-4 mt-4">
              <div>
                <label className="text-sm font-medium">Company Name *</label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div>
                <label className="text-sm font-medium">Email *</label>
                <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Phone</label>
                  <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </div>
                <div>
                  <label className="text-sm font-medium">Country *</label>
                  <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} required />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">City</label>
                <Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-medium">Categories (comma-separated)</label>
                <Input value={form.categories} onChange={(e) => setForm({ ...form, categories: e.target.value })} placeholder="Electronics, Raw Materials" />
              </div>
              <Button type="submit" className="w-full">{editingSupplier ? "Update" : "Create"} Supplier</Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input className="pl-9" placeholder="Search suppliers..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 rounded-xl bg-white border animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((supplier) => (
            <Card
              key={supplier.id}
              className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => openEdit(supplier)}
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-foreground">{supplier.name}</h3>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
                      <MapPin className="w-3 h-3" />
                      {supplier.city ? `${supplier.city}, ` : ""}{supplier.country}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-amber-500">
                    <Star className="w-4 h-4 fill-current" />
                    <span className="text-sm font-medium">{supplier.rating?.toFixed(1) || "N/A"}</span>
                  </div>
                </div>

                <div className="space-y-2 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Mail className="w-3.5 h-3.5" /> {supplier.email}
                  </div>
                  {supplier.phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="w-3.5 h-3.5" /> {supplier.phone}
                    </div>
                  )}
                </div>

                {supplier.categories?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {supplier.categories.slice(0, 3).map((cat) => (
                      <Badge key={cat.id} variant="secondary" className="text-xs">
                        {cat.category_name}
                      </Badge>
                    ))}
                    {supplier.categories.length > 3 && (
                      <Badge variant="outline" className="text-xs">+{supplier.categories.length - 3}</Badge>
                    )}
                  </div>
                )}

                <div className="mt-3 pt-3 border-t flex items-center justify-between text-xs text-muted-foreground">
                  <span>Added {formatDate(supplier.created_at)}</span>
                  <Badge className={supplier.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}>
                    {supplier.status}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <Users className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No suppliers found</p>
        </div>
      )}
    </div>
  );
}
