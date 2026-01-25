import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Package, Tag, Euro, Filter } from 'lucide-react';
import { productsApi, growPlansApi, productGroupsApi } from '../services/api';
import { Product, ProductCategory, GrowPlan, ProductGroup } from '../types';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
  Button,
  Input,
  Select,
  Modal,
  ConfirmDialog,
  PageLoader,
  EmptyState,
  useToast,
  Badge,
  SelectOption,
  Tabs,
} from '../components/ui';

const CATEGORY_LABELS: Record<ProductCategory, string> = {
  MICROGREEN: 'Microgreens',
  SEED: 'Saatgut',
  PACKAGING: 'Verpackung',
  BUNDLE: 'Bundle',
};

const CATEGORY_COLORS: Record<ProductCategory, 'green' | 'blue' | 'gray' | 'purple'> = {
  MICROGREEN: 'green',
  SEED: 'blue',
  PACKAGING: 'gray',
  BUNDLE: 'purple',
};

export default function Products() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterActive, setFilterActive] = useState<string>('true');
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [deletingProduct, setDeletingProduct] = useState<Product | null>(null);
  const [activeTab, setActiveTab] = useState('products');

  // Fetch products
  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products', { category: filterCategory, is_active: filterActive }],
    queryFn: () =>
      productsApi.list({
        category: filterCategory === 'all' ? undefined : filterCategory,
        is_active: filterActive === 'all' ? undefined : filterActive === 'true',
      }),
  });

  // Fetch grow plans
  const { data: growPlans = [] } = useQuery({
    queryKey: ['grow-plans'],
    queryFn: () => growPlansApi.list(),
  });

  // Fetch product groups
  const { data: productGroups = [] } = useQuery({
    queryKey: ['product-groups'],
    queryFn: () => productGroupsApi.list(),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => productsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      toast.success('Produkt deaktiviert');
      setDeletingProduct(null);
    },
    onError: () => {
      toast.error('Fehler beim Deaktivieren');
    },
  });

  const filteredProducts = products.filter(
    (product) =>
      product.name.toLowerCase().includes(search.toLowerCase()) ||
      product.sku.toLowerCase().includes(search.toLowerCase())
  );

  const categoryOptions: SelectOption[] = [
    { value: 'all', label: 'Alle Kategorien' },
    { value: 'MICROGREEN', label: 'Microgreens' },
    { value: 'SEED', label: 'Saatgut' },
    { value: 'PACKAGING', label: 'Verpackung' },
    { value: 'BUNDLE', label: 'Bundle' },
  ];

  const activeOptions: SelectOption[] = [
    { value: 'all', label: 'Alle' },
    { value: 'true', label: 'Nur aktive' },
    { value: 'false', label: 'Nur inaktive' },
  ];

  const tabs = [
    { id: 'products', label: 'Produkte', count: products.length },
    { id: 'growplans', label: 'Wachstumspläne', count: growPlans.length },
    { id: 'groups', label: 'Produktgruppen', count: productGroups.length },
  ];

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div>
      <PageHeader
        title="Produktverwaltung"
        subtitle={`${products.length} Produkte`}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
            Neues Produkt
          </Button>
        }
      />

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} className="mb-6" />

      {activeTab === 'products' && (
        <>
          <FilterBar>
            <div className="flex-1 max-w-md">
              <Input
                placeholder="Suchen nach Name oder SKU..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                prefix={<Search className="w-4 h-4" />}
              />
            </div>
            <Select
              options={categoryOptions}
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
            />
            <Select
              options={activeOptions}
              value={filterActive}
              onChange={(e) => setFilterActive(e.target.value)}
            />
          </FilterBar>

          {filteredProducts.length === 0 ? (
            <EmptyState
              title="Keine Produkte gefunden"
              description={search ? 'Versuche eine andere Suche.' : 'Erstelle dein erstes Produkt.'}
              action={
                !search && (
                  <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
                    Erstes Produkt anlegen
                  </Button>
                )
              }
            />
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Produkt
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Kategorie
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Preis
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      MwSt
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Aktionen
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredProducts.map((product) => (
                    <tr key={product.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10 bg-gray-100 rounded-lg flex items-center justify-center">
                            <Package className="h-5 w-5 text-gray-500" />
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">{product.name}</div>
                            <div className="text-sm text-gray-500">{product.sku}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge color={CATEGORY_COLORS[product.category]}>
                          {CATEGORY_LABELS[product.category]}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {product.base_price ? `${product.base_price.toFixed(2)} €` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {product.tax_rate === 'REDUZIERT' ? '7%' : product.tax_rate === 'STANDARD' ? '19%' : '0%'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge color={product.is_active ? 'green' : 'gray'}>
                          {product.is_active ? 'Aktiv' : 'Inaktiv'}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingProduct(product)}
                        >
                          Bearbeiten
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeletingProduct(product)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Deaktivieren
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {activeTab === 'growplans' && (
        <GrowPlansTab growPlans={growPlans} />
      )}

      {activeTab === 'groups' && (
        <ProductGroupsTab groups={productGroups} />
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={isCreating || !!editingProduct}
        onClose={() => {
          setIsCreating(false);
          setEditingProduct(null);
        }}
        title={editingProduct ? 'Produkt bearbeiten' : 'Neues Produkt'}
        size="lg"
      >
        <ProductForm
          product={editingProduct}
          growPlans={growPlans}
          productGroups={productGroups}
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['products'] });
            setIsCreating(false);
            setEditingProduct(null);
            toast.success(editingProduct ? 'Produkt aktualisiert' : 'Produkt erstellt');
          }}
          onCancel={() => {
            setIsCreating(false);
            setEditingProduct(null);
          }}
        />
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deletingProduct}
        onClose={() => setDeletingProduct(null)}
        onConfirm={() => deletingProduct && deleteMutation.mutate(deletingProduct.id)}
        title="Produkt deaktivieren?"
        message={`Möchtest du "${deletingProduct?.name}" wirklich deaktivieren?`}
        confirmLabel="Deaktivieren"
        variant="danger"
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

// Product Form
interface ProductFormProps {
  product: Product | null;
  growPlans: GrowPlan[];
  productGroups: ProductGroup[];
  onSubmit: () => void;
  onCancel: () => void;
}

function ProductForm({ product, growPlans, productGroups, onSubmit, onCancel }: ProductFormProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    sku: product?.sku || '',
    name: product?.name || '',
    category: product?.category || 'MICROGREEN',
    description: product?.description || '',
    product_group_id: product?.product_group_id || '',
    base_price: product?.base_price || 0,
    tax_rate: product?.tax_rate || 'REDUZIERT',
    grow_plan_id: product?.grow_plan_id || '',
    shelf_life_days: product?.shelf_life_days || 7,
    is_active: product?.is_active ?? true,
    is_sellable: product?.is_sellable ?? true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const data = {
        ...formData,
        product_group_id: formData.product_group_id || null,
        grow_plan_id: formData.grow_plan_id || null,
      };

      if (product) {
        await productsApi.update(product.id, data);
      } else {
        await productsApi.create(data);
      }
      onSubmit();
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setLoading(false);
    }
  };

  const categoryOptions: SelectOption[] = [
    { value: 'MICROGREEN', label: 'Microgreens' },
    { value: 'SEED', label: 'Saatgut' },
    { value: 'PACKAGING', label: 'Verpackung' },
    { value: 'BUNDLE', label: 'Bundle' },
  ];

  const taxOptions: SelectOption[] = [
    { value: 'REDUZIERT', label: '7% (Lebensmittel)' },
    { value: 'STANDARD', label: '19% (Standard)' },
    { value: 'STEUERFREI', label: '0% (Steuerfrei)' },
  ];

  const groupOptions: SelectOption[] = [
    { value: '', label: 'Keine Gruppe' },
    ...productGroups.map((g) => ({ value: g.id, label: g.name })),
  ];

  const planOptions: SelectOption[] = [
    { value: '', label: 'Kein Wachstumsplan' },
    ...growPlans.map((p) => ({ value: p.id, label: p.name })),
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="SKU"
          required
          value={formData.sku}
          onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
          placeholder="z.B. MG-0001"
        />
        <Input
          label="Name"
          required
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="z.B. Sonnenblume Microgreens"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Select
          label="Kategorie"
          options={categoryOptions}
          value={formData.category}
          onChange={(e) => setFormData({ ...formData, category: e.target.value as ProductCategory })}
        />
        <Select
          label="Produktgruppe"
          options={groupOptions}
          value={formData.product_group_id}
          onChange={(e) => setFormData({ ...formData, product_group_id: e.target.value })}
        />
      </div>

      <Input
        label="Beschreibung"
        value={formData.description}
        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
        placeholder="Produktbeschreibung..."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Input
          label="Basispreis"
          type="number"
          step="0.01"
          min={0}
          value={formData.base_price}
          onChange={(e) => setFormData({ ...formData, base_price: Number(e.target.value) })}
          suffix="€"
        />
        <Select
          label="Steuersatz"
          options={taxOptions}
          value={formData.tax_rate}
          onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value })}
        />
        <Input
          label="Haltbarkeit"
          type="number"
          min={1}
          value={formData.shelf_life_days}
          onChange={(e) => setFormData({ ...formData, shelf_life_days: Number(e.target.value) })}
          suffix="Tage"
        />
      </div>

      {formData.category === 'MICROGREEN' && (
        <Select
          label="Wachstumsplan"
          options={planOptions}
          value={formData.grow_plan_id}
          onChange={(e) => setFormData({ ...formData, grow_plan_id: e.target.value })}
        />
      )}

      <div className="flex gap-4">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={formData.is_active}
            onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
          />
          <span className="text-sm text-gray-700">Aktiv</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={formData.is_sellable}
            onChange={(e) => setFormData({ ...formData, is_sellable: e.target.checked })}
            className="w-4 h-4 rounded border-gray-300 text-minga-600 focus:ring-minga-500"
          />
          <span className="text-sm text-gray-700">Verkäuflich</span>
        </label>
      </div>

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button type="submit" loading={loading} fullWidth>
          {product ? 'Speichern' : 'Erstellen'}
        </Button>
      </div>
    </form>
  );
}

// Grow Plans Tab
function GrowPlansTab({ growPlans }: { growPlans: GrowPlan[] }) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keimung</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Wachstum</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Erntefenster</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ertrag/Tray</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {growPlans.map((plan) => (
            <tr key={plan.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm font-mono text-gray-900">{plan.code}</td>
              <td className="px-6 py-4 text-sm text-gray-900">{plan.name}</td>
              <td className="px-6 py-4 text-sm text-gray-500">{plan.germination_days} Tage</td>
              <td className="px-6 py-4 text-sm text-gray-500">{plan.growth_days} Tage</td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {plan.harvest_window_start_days}-{plan.harvest_window_end_days} Tage
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">{plan.expected_yield_grams_per_tray}g</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Product Groups Tab
function ProductGroupsTab({ groups }: { groups: ProductGroup[] }) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Beschreibung</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {groups.map((group) => (
            <tr key={group.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm font-mono text-gray-900">{group.code}</td>
              <td className="px-6 py-4 text-sm text-gray-900">{group.name}</td>
              <td className="px-6 py-4 text-sm text-gray-500">{group.description || '-'}</td>
              <td className="px-6 py-4">
                <Badge color={group.is_active ? 'green' : 'gray'}>
                  {group.is_active ? 'Aktiv' : 'Inaktiv'}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
