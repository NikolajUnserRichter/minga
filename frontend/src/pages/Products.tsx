import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Package, Trash } from 'lucide-react';
import { productsApi, growPlansApi, productGroupsApi, unitsApi } from '../services/api';
import { Product, ProductCategory, GrowPlan, ProductGroup, ProductVariant, UnitOfMeasure } from '../types';
import { ExcelImport } from '../components/common/ExcelImport';
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

const CATEGORY_COLORS: Record<ProductCategory, 'success' | 'info' | 'gray' | 'purple'> = {
  MICROGREEN: 'success',
  SEED: 'info',
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
          <div className="flex gap-2 items-center">
            <ExcelImport entity="products" onImported={() => queryClient.invalidateQueries({ queryKey: ['products'] })} />
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setIsCreating(true)}>
              Neues Produkt
            </Button>
          </div>
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
                startIcon={<Search className="w-4 h-4" />}
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
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-700/50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Produkt
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Kategorie
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Preis
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      MwSt
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Aktionen
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {filteredProducts.map((product) => (
                    <tr key={product.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center">
                            <Package className="h-5 w-5 text-gray-500 dark:text-gray-400" />
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900 dark:text-white">{product.name}</div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">{product.sku}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant={CATEGORY_COLORS[product.category]}>
                          {CATEGORY_LABELS[product.category]}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                        {product.base_price !== null && product.base_price !== undefined ? `${Number(product.base_price).toFixed(2)} €` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {product.tax_rate === 'REDUZIERT' ? '7%' : product.tax_rate === 'STANDARD' ? '19%' : '0%'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant={product.is_active ? 'success' : 'gray'}>
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
                          className="text-red-600 dark:text-red-400 hover:text-red-900"
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
    gtin: product?.gtin || '',
    old_article_number: product?.old_article_number || '',
    certification: product?.certification || '',
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
        gtin: formData.gtin || null,
        old_article_number: formData.old_article_number || null,
        certification: formData.certification || null,
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

  const certificationOptions: SelectOption[] = [
    { value: '', label: 'Keine Zertifizierung' },
    { value: 'BIO', label: 'BIO' },
    { value: 'KONVENTIONELL', label: 'Konventionell' },
    { value: 'TRANSITIONAL', label: 'Umstellung' },
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Input
          label="GTIN / EAN"
          value={formData.gtin}
          onChange={(e) => setFormData({ ...formData, gtin: e.target.value })}
          placeholder="4012345678901"
        />
        <Input
          label="Alte Artikelnummer"
          value={formData.old_article_number}
          onChange={(e) => setFormData({ ...formData, old_article_number: e.target.value })}
          placeholder="aus Altsystem"
        />
        <Select
          label="Zertifizierung"
          options={certificationOptions}
          value={formData.certification}
          onChange={(e) => setFormData({ ...formData, certification: e.target.value })}
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
          endIcon="€"
        />
        <Select
          label="Steuersatz"
          options={taxOptions}
          value={formData.tax_rate}
          onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value as any })}
        />
        <Input
          label="Haltbarkeit"
          type="number"
          min={1}
          value={formData.shelf_life_days}
          onChange={(e) => setFormData({ ...formData, shelf_life_days: Number(e.target.value) })}
          endIcon="Tage"
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
            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">Aktiv</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={formData.is_sellable}
            onChange={(e) => setFormData({ ...formData, is_sellable: e.target.checked })}
            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">Verkäuflich</span>
        </label>
      </div>

      {product && <VariantList productId={product.id} />}

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

function VariantList({ productId }: { productId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: variants = [] } = useQuery({
    queryKey: ['product-variants', productId],
    queryFn: () => productsApi.listVariants(productId),
  });
  const { data: units = [] } = useQuery({
    queryKey: ['units'],
    queryFn: () => unitsApi.list(),
  });

  const containerUnits = units.filter((u) => u.category === 'CONTAINER' || u.category === 'WEIGHT' || u.category === 'COUNT');
  const unitOptions: SelectOption[] = [
    { value: '', label: 'Einheit wählen…' },
    ...containerUnits.map((u: UnitOfMeasure) => ({ value: u.id, label: `${u.code} — ${u.name}` })),
  ];

  const [newVariant, setNewVariant] = useState<Partial<ProductVariant>>({
    packaging_unit_id: '',
    items_per_pack: 1,
    sku_suffix: '',
    name_suffix: '',
    price_override: null,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['product-variants', productId] });

  const addMutation = useMutation({
    mutationFn: () => productsApi.createVariant(productId, newVariant),
    onSuccess: () => {
      invalidate();
      setNewVariant({ packaging_unit_id: '', items_per_pack: 1, sku_suffix: '', name_suffix: '', price_override: null });
      toast.success('Variante hinzugefügt');
    },
    onError: () => toast.error('Fehler beim Hinzufügen'),
  });

  const deleteMutation = useMutation({
    mutationFn: (variantId: string) => productsApi.deleteVariant(productId, variantId),
    onSuccess: () => {
      invalidate();
      toast.success('Variante gelöscht');
    },
  });

  return (
    <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
      <legend className="px-2 text-sm font-medium text-gray-700 dark:text-gray-300">
        Verpackungs-Varianten ({variants.length})
      </legend>

      {variants.length > 0 && (
        <div className="space-y-2">
          {variants.map((v) => (
            <div key={v.id} className="flex items-center gap-2 text-sm bg-gray-50 dark:bg-gray-700/50 rounded px-3 py-2">
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-white">
                  {v.name_suffix || v.packaging_unit_name} {v.sku_suffix && <span className="text-xs text-gray-500">({v.sku_suffix})</span>}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {v.items_per_pack} × {v.packaging_unit_code} · {v.price_override !== null ? `€${v.price_override}` : 'Basispreis'}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                icon={<Trash className="w-4 h-4" />}
                onClick={() => deleteMutation.mutate(v.id)}
              />
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
        <Select
          options={unitOptions}
          value={newVariant.packaging_unit_id || ''}
          onChange={(e) => setNewVariant({ ...newVariant, packaging_unit_id: e.target.value })}
        />
        <Input
          type="number"
          placeholder="Stk/Pack"
          value={newVariant.items_per_pack || 1}
          onChange={(e) => setNewVariant({ ...newVariant, items_per_pack: Number(e.target.value) })}
          min={1}
        />
        <Input
          placeholder="SKU-Suffix"
          value={newVariant.sku_suffix || ''}
          onChange={(e) => setNewVariant({ ...newVariant, sku_suffix: e.target.value })}
        />
        <Input
          placeholder="Name (z.B. 12er Kiste)"
          value={newVariant.name_suffix || ''}
          onChange={(e) => setNewVariant({ ...newVariant, name_suffix: e.target.value })}
        />
        <Input
          type="number"
          step="0.01"
          placeholder="Preis (optional)"
          value={newVariant.price_override ?? ''}
          onChange={(e) => setNewVariant({ ...newVariant, price_override: e.target.value ? Number(e.target.value) : null })}
        />
      </div>
      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          icon={<Plus className="w-4 h-4" />}
          disabled={!newVariant.packaging_unit_id}
          onClick={() => addMutation.mutate()}
        >
          Hinzufügen
        </Button>
      </div>
    </fieldset>
  );
}

// Grow Plans Tab — list + create
function GrowPlansTab({ growPlans }: { growPlans: GrowPlan[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
          Neuer Wachstumsplan
        </Button>
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-700/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Code</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Keimung</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Wachstum</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Erntefenster</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Ertrag/Kiste</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {growPlans.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-8 text-sm text-center text-gray-500 dark:text-gray-400">Keine Wachstumspläne — lege deinen ersten an</td></tr>
            ) : growPlans.map((plan) => (
              <tr key={plan.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
                <td className="px-6 py-4 text-sm font-mono text-gray-900 dark:text-white">{plan.code}</td>
                <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">{plan.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{plan.germination_days} Tage</td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{plan.growth_days} Tage</td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                  {plan.harvest_window_start_days}-{plan.harvest_window_end_days} Tage
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{plan.expected_yield_grams_per_tray}g</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={creating} onClose={() => setCreating(false)} title="Neuer Wachstumsplan" size="lg">
        <GrowPlanForm
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['grow-plans'] });
            setCreating(false);
            toast.success('Wachstumsplan angelegt');
          }}
          onCancel={() => setCreating(false)}
        />
      </Modal>
    </div>
  );
}

// Product Groups Tab — list + create
function ProductGroupsTab({ groups }: { groups: ProductGroup[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreating(true)}>
          Neue Produktgruppe
        </Button>
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-700/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Code</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Beschreibung</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {groups.length === 0 ? (
              <tr><td colSpan={4} className="px-6 py-8 text-sm text-center text-gray-500 dark:text-gray-400">Keine Produktgruppen — lege deine erste an</td></tr>
            ) : groups.map((group) => (
              <tr key={group.id} className="hover:bg-gray-50 dark:bg-gray-700/50">
                <td className="px-6 py-4 text-sm font-mono text-gray-900 dark:text-white">{group.code}</td>
                <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">{group.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{group.description || '-'}</td>
                <td className="px-6 py-4">
                  <Badge variant={group.is_active ? 'success' : 'gray'}>
                    {group.is_active ? 'Aktiv' : 'Inaktiv'}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={creating} onClose={() => setCreating(false)} title="Neue Produktgruppe">
        <ProductGroupForm
          onSubmit={() => {
            queryClient.invalidateQueries({ queryKey: ['product-groups'] });
            setCreating(false);
            toast.success('Produktgruppe angelegt');
          }}
          onCancel={() => setCreating(false)}
        />
      </Modal>
    </div>
  );
}

function GrowPlanForm({ onSubmit, onCancel }: { onSubmit: () => void; onCancel: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [d, setD] = useState({
    code: '',
    name: '',
    description: '',
    soak_hours: 0,
    blackout_days: 0,
    germination_days: 2,
    growth_days: 7,
    harvest_window_start_days: 9,
    harvest_window_optimal_days: 10,
    harvest_window_end_days: 12,
    expected_yield_grams_per_tray: 350,
    expected_loss_percent: 5,
    seed_density_grams_per_tray: 12,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await growPlansApi.create(d);
      onSubmit();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Fehler beim Speichern');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Input label="Code" required value={d.code} onChange={(e) => setD({ ...d, code: e.target.value })} placeholder="z.B. MG-SONNE-STD" />
        <Input label="Name" required value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder="z.B. Sonnenblume Standard" />
      </div>
      <Input label="Beschreibung" value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })} />

      <div className="grid grid-cols-3 gap-4">
        <Input label="Einweichen" type="number" min={0} value={d.soak_hours} onChange={(e) => setD({ ...d, soak_hours: Number(e.target.value) })} endIcon="h" />
        <Input label="Dunkelphase" type="number" min={0} value={d.blackout_days} onChange={(e) => setD({ ...d, blackout_days: Number(e.target.value) })} endIcon="Tage" />
        <Input label="Saatdichte" type="number" min={0} step={0.1} value={d.seed_density_grams_per_tray} onChange={(e) => setD({ ...d, seed_density_grams_per_tray: Number(e.target.value) })} endIcon="g" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Input label="Keimdauer" type="number" required min={1} value={d.germination_days} onChange={(e) => setD({ ...d, germination_days: Number(e.target.value) })} endIcon="Tage" />
        <Input label="Wachstumsdauer" type="number" required min={1} value={d.growth_days} onChange={(e) => setD({ ...d, growth_days: Number(e.target.value) })} endIcon="Tage" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Input label="Ernte ab" type="number" required min={1} value={d.harvest_window_start_days} onChange={(e) => setD({ ...d, harvest_window_start_days: Number(e.target.value) })} endIcon="Tage" />
        <Input label="Optimal" type="number" required min={1} value={d.harvest_window_optimal_days} onChange={(e) => setD({ ...d, harvest_window_optimal_days: Number(e.target.value) })} endIcon="Tage" />
        <Input label="Ernte bis" type="number" required min={1} value={d.harvest_window_end_days} onChange={(e) => setD({ ...d, harvest_window_end_days: Number(e.target.value) })} endIcon="Tage" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Input label="Erwarteter Ertrag" type="number" required min={1} value={d.expected_yield_grams_per_tray} onChange={(e) => setD({ ...d, expected_yield_grams_per_tray: Number(e.target.value) })} endIcon="g/Kiste" />
        <Input label="Verlustquote" type="number" min={0} max={100} value={d.expected_loss_percent} onChange={(e) => setD({ ...d, expected_loss_percent: Number(e.target.value) })} endIcon="%" />
      </div>

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>Abbrechen</Button>
        <Button type="submit" loading={loading} fullWidth>Anlegen</Button>
      </div>
    </form>
  );
}

function ProductGroupForm({ onSubmit, onCancel }: { onSubmit: () => void; onCancel: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [d, setD] = useState({ code: '', name: '', description: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await productGroupsApi.create(d);
      onSubmit();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Fehler beim Speichern');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Input label="Code" required value={d.code} onChange={(e) => setD({ ...d, code: e.target.value })} placeholder="z.B. MICROGREEN" />
        <Input label="Name" required value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder="z.B. Microgreens" />
      </div>
      <Input label="Beschreibung" value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })} />

      <div className="flex gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onCancel}>Abbrechen</Button>
        <Button type="submit" loading={loading} fullWidth>Anlegen</Button>
      </div>
    </form>
  );
}
