import { useEffect, useState } from "react";
import { api, type Page } from "../../api/client";
import { FiX, FiPackage, FiBox, FiAlertTriangle, FiXCircle, FiTruck, FiRepeat, FiCheck, FiSearch, FiFilter, FiArrowRight } from "react-icons/fi";

// --- API DATA TYPES ---
interface DashboardKpis {
  total_products: number;
  low_stock_count: number;
  out_of_stock_count: number;
  deliveries_today: number;
}

interface ApiProduct {
  id: number;
  name: string;
  sku: string;
  category: string;
  stock_count: number;
  min_stock: number;
  unit_price_ron: number;
  status: 'OK' | 'LOW' | 'OUT';
  shortfall: number;
}

interface FlowData {
  nodes: { name: string; type?: string }[];
  links: { source: number; target: number; value: number; items: string }[];
  date_range?: { start: string; end: string };
}

// --- LOGISTICS TRACE OVERVIEW ---
// --- LOGISTICS TRACE OVERVIEW ---
// --- LOGISTICS TRACE OVERVIEW ---
function LogisticsOverview({ data }: { data: FlowData }) {
  const inboundMap: Record<number, { supplier: string; volume: number; details: string[] }> = {};
  const outboundMap: Record<number, { destination: string; volume: number; details: string[] }> = {};
  const productMap: Record<string, { inbound: { s: string; v: number }[]; outbound: { d: string; v: number }[]; totalIn: number; totalOut: number }> = {};

  // Initialize product map from nodes
  data.nodes.filter(n => n.type === 'product').forEach(p => {
    productMap[p.name] = { inbound: [], outbound: [], totalIn: 0, totalOut: 0 };
  });

  data.links.forEach(l => {
    const sourceNode = data.nodes[l.source];
    const targetNode = data.nodes[l.target];
    const pName = (l as any).product_name;

    // Supplier -> Product
    if (sourceNode?.type === 'supplier') {
      if (!inboundMap[l.source]) inboundMap[l.source] = { supplier: sourceNode.name, volume: 0, details: [] };
      inboundMap[l.source].volume += l.value;
      inboundMap[l.source].details.push(l.items ? l.items : `${targetNode?.name || 'Items'} (${l.value})`);
      
      if (pName && productMap[pName]) {
        productMap[pName].inbound.push({ s: sourceNode.name, v: l.value });
        productMap[pName].totalIn += l.value;
      }
    }

    // Warehouse -> Outbound
    if (targetNode?.type === 'out') {
      if (!outboundMap[l.target]) outboundMap[l.target] = { destination: targetNode.name, volume: 0, details: [] };
      outboundMap[l.target].volume += l.value;
      outboundMap[l.target].details.push(l.items ? l.items : `Items (${l.value})`);

      if (pName && productMap[pName]) {
        productMap[pName].outbound.push({ d: targetNode.name, v: l.value });
        productMap[pName].totalOut += l.value;
      }
    }
  });

  const inboundList = Object.values(inboundMap).sort((a, b) => b.volume - a.volume);
  const outboundList = Object.values(outboundMap).sort((a, b) => b.volume - a.volume);
  const productList = Object.entries(productMap)
    .filter(([_, pd]) => pd.totalIn > 0 || pd.totalOut > 0)
    .map(([name, pd]) => ({ name, ...pd }))
    .sort((a, b) => (b.totalIn + b.totalOut) - (a.totalIn + a.totalOut));

  const renderTraceCard = (title: string, icon: any, list: any[], accentText: string, accentBg: string, mode: 'in' | 'out' | 'prod') => {
    const Icon = icon;
    return (
      <div className="flex-1 bg-[var(--card)] rounded-2xl border border-[var(--border)] overflow-hidden flex flex-col max-h-[600px]">
        <div className="px-5 py-4 border-b border-[var(--border)] flex items-center gap-3 shrink-0 bg-[var(--input-background)]">
          <div className={`w-10 h-10 rounded-xl bg-[var(--card)] border border-[var(--border)] grid place-items-center ${accentText}`}>
            <Icon size={18} />
          </div>
          <div>
            <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">{title}</h3>
            <p className="text-sm font-semibold mt-0.5">{list.length} active records</p>
          </div>
        </div>

        <div className="divide-y divide-[var(--border)] overflow-y-auto flex-1 slim-scroll">
          {list.length > 0 ? list.map((item, i) => (
            <div key={i} className="p-4 hover:bg-[var(--input-background)] transition-colors">
              {mode !== 'prod' ? (
                <>
                  <div className="flex justify-between items-start mb-2.5 gap-3">
                    <h4 className="text-sm font-semibold">{mode === 'out' ? item.destination : item.supplier}</h4>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${accentBg} ${accentText} border border-current/20`}>
                      {item.volume.toLocaleString()} units
                    </span>
                  </div>
                  <div className="bg-[var(--input-background)] rounded-lg p-2.5 border border-[var(--border)]">
                    <p className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1.5">
                      {mode === 'out' ? 'Items Sent' : 'Items Received'}
                    </p>
                    <ul className="space-y-1">
                      {item.details.map((detail: string, j: number) => (
                        <li key={j} className="text-xs text-[var(--muted-foreground)] flex items-start gap-2">
                          <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${mode === 'out' ? 'bg-rose-400' : 'bg-emerald-400'}`} />
                          {detail}
                        </li>
                      ))}
                    </ul>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex justify-between items-start mb-2.5 gap-3">
                    <h4 className="text-sm font-semibold">{item.name}</h4>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${accentBg} ${accentText} border border-current/20`}>
                      {(item.totalIn + item.totalOut).toLocaleString()} moved
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-emerald-50 rounded-lg p-2 border border-emerald-200/60">
                      <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-[0.14em] mb-1">In ({item.totalIn})</p>
                      {item.inbound.length > 0 ? item.inbound.map((inc: any, j: number) => (
                        <p key={j} className="text-[11px] text-[var(--muted-foreground)] truncate" title={inc.s}>• {inc.s} ({inc.v})</p>
                      )) : <p className="text-[11px] text-[var(--muted-foreground)] italic">None</p>}
                    </div>
                    <div className="bg-rose-50 rounded-lg p-2 border border-rose-200/60">
                      <p className="text-[10px] font-semibold text-rose-700 uppercase tracking-[0.14em] mb-1">Out ({item.totalOut})</p>
                      {item.outbound.length > 0 ? item.outbound.map((outc: any, j: number) => (
                        <p key={j} className="text-[11px] text-[var(--muted-foreground)] truncate" title={outc.d}>• {outc.d} ({outc.v})</p>
                      )) : <p className="text-[11px] text-[var(--muted-foreground)] italic">None</p>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )) : (
            <div className="text-sm text-[var(--muted-foreground)] py-8 text-center italic">No movement data available</div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="relative">
      <style>{`
        .slim-scroll::-webkit-scrollbar {
          width: 6px;
        }
        .slim-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .slim-scroll::-webkit-scrollbar-thumb {
          background-color: var(--border);
          border-radius: 20px;
        }
        .slim-scroll {
          scrollbar-width: thin;
          scrollbar-color: var(--border) transparent;
        }
      `}</style>
      <div className="flex flex-col lg:flex-row gap-4 h-[600px]">
        {renderTraceCard('Suppliers Trace', FiTruck, inboundList, 'text-emerald-700', 'bg-emerald-50', 'in')}
        {renderTraceCard('Product Trace', FiPackage, productList, 'text-[var(--primary)]', 'bg-[var(--primary)]/10', 'prod')}
        {renderTraceCard('Destinations Trace', FiArrowRight, outboundList, 'text-rose-700', 'bg-rose-50', 'out')}
      </div>
    </div>
  );
}

// --- UI COMPONENTS ---
const KPICard = ({ label, value, sub, icon: Icon }: any) => (
  <article className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 flex items-start justify-between gap-3">
    <div className="flex flex-col">
      <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{label}</p>
      <p className="text-2xl font-semibold mt-1 tracking-tight">{value}</p>
      {sub && <p className="text-xs text-[var(--muted-foreground)] mt-1">{sub}</p>}
    </div>
    <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
      <Icon size={18} />
    </div>
  </article>
);

const StatusBadge = ({ status }: { status: string }) => {
  const styles: Record<string, string> = {
    OK: "bg-emerald-50 text-emerald-700 border-emerald-200",
    LOW: "bg-amber-50 text-amber-700 border-amber-200",
    OUT: "bg-rose-50 text-rose-700 border-rose-200",
  };
  const label: Record<string, string> = { OK: 'Healthy', LOW: 'Low Stock', OUT: 'Depleted' };
  const icons: Record<string, any> = { OK: FiCheck, LOW: FiAlertTriangle, OUT: FiXCircle };
  const Icon = icons[status] || FiBox;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status] ?? "bg-[var(--input-background)] text-[var(--muted-foreground)] border-[var(--border)]"}`}>
      <Icon size={12} />
      {label[status] ?? status}
    </span>
  );
};

const DetailDrawer = ({ open, onClose, product }: { open: boolean, onClose: () => void, product: ApiProduct | null }) => {
  return (
    <>
      <div
        className={`fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />
      <div className={`fixed inset-y-0 right-0 w-full max-w-md bg-[var(--card)] border-l border-[var(--border)] z-50 transform transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="p-5 border-b border-[var(--border)] flex items-center justify-between sticky top-0 z-10 bg-[var(--card)]">
          <div>
            <h2 className="text-[1.05rem] font-semibold tracking-tight">{product?.name}</h2>
            <p className="text-sm text-[var(--muted-foreground)] flex items-center gap-2 mt-1">
              <span className="bg-[var(--input-background)] px-2 py-0.5 rounded text-xs font-mono">{product?.sku}</span>
              · {product?.category}
            </p>
          </div>
          <button onClick={onClose} className="p-2 bg-[var(--input-background)] hover:bg-[var(--border)] rounded-full text-[var(--muted-foreground)] transition-colors">
            <FiX size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {product && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--input-background)]">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-1">Current Stock</p>
                  <p className="text-2xl font-semibold tracking-tight">{product.stock_count}</p>
                </div>
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--input-background)]">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-1">Status</p>
                  <div className="mt-2"><StatusBadge status={product.status} /></div>
                </div>
              </div>

              <div className="space-y-2.5 py-4 border-t border-b border-[var(--border)]">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-[var(--muted-foreground)]">Minimum Threshold</span>
                  <span className="text-sm font-semibold">{product.min_stock} units</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-[var(--muted-foreground)]">Unit Price</span>
                  <span className="text-sm font-semibold">{(product.unit_price_ron || 0).toFixed(2)} RON</span>
                </div>
                {product.status !== 'OK' && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-[var(--muted-foreground)]">Shortfall</span>
                    <span className="text-sm font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">{product.shortfall} units</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

// --- MAIN DASHBOARD COMPONENT ---
export default function InventoryDashboard() {
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [selectedProduct, setSelectedProduct] = useState<ApiProduct | null>(null);
  const [flowData, setFlowData] = useState<FlowData | null>(null);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [totalProducts, setTotalProducts] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    api.get<DashboardKpis>('/api/inventory/dashboard/')
      .then(setKpis)
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }, []);

  useEffect(() => {
    setLoadingProducts(true);
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (category !== 'All') params.append('category', category);
    if (statusFilter !== 'All') params.append('status', statusFilter);
    params.append('page', page.toString());

    api.get<Page<ApiProduct>>(`/api/inventory/products/?${params.toString()}`)
      .then(data => {
        setProducts(data.results);
        setTotalProducts(data.count);
      })
      .catch(() => {
        setProducts([]);
        setTotalProducts(0);
      })
      .finally(() => setLoadingProducts(false))
  }, [search, category, statusFilter, page]);

  useEffect(() => {
    api.get<FlowData>('/api/inventory/flow/', { days: 7 })
      .then(setFlowData)
      .catch(() => undefined)
  }, []);

  return (
    <div className="space-y-6">

      {/* KPI GRID */}
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <header className="mb-4">
          <h2 className="text-[1.05rem] font-semibold tracking-tight">Inventory Dashboard</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">Real-time inventory metrics and forecasting.</p>
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <KPICard
            label="Total Products"
            value={loading ? "…" : (kpis?.total_products ?? 0)}
            sub="active SKUs"
            icon={FiBox}
          />
          <KPICard
            label="Low Stock Items"
            value={loading ? "…" : (kpis?.low_stock_count ?? 0)}
            sub="below threshold"
            icon={FiAlertTriangle}
          />
          <KPICard
            label="Out of Stock"
            value={loading ? "…" : (kpis?.out_of_stock_count ?? 0)}
            sub="needs restock"
            icon={FiXCircle}
          />
          <KPICard
            label="Deliveries Today"
            value={loading ? "…" : (kpis?.deliveries_today ?? 0)}
            sub="expected arrivals"
            icon={FiTruck}
          />
        </div>
      </section>

      {/* STOCK MOVEMENT FLOW */}
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <header className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
              <FiRepeat size={18} />
            </div>
            <div>
              <h2 className="text-[1.05rem] font-semibold tracking-tight">Stock Movement Flow</h2>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">Inbound suppliers, product traces and outbound destinations.</p>
            </div>
          </div>
          {flowData?.date_range && (
            <span className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] bg-[var(--input-background)] px-2.5 py-1 rounded-full border border-[var(--border)] whitespace-nowrap">
              {new Date(flowData.date_range.start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – {new Date(flowData.date_range.end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
        </header>
        {flowData && flowData.nodes && flowData.nodes.length > 0 ? (
          <LogisticsOverview data={flowData} />
        ) : (
          <div className="flex items-center justify-center h-40 text-[var(--muted-foreground)] animate-pulse">Loading logistics...</div>
        )}
      </section>

      {/* PRODUCTS TABLE */}
      <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between border-b border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
              <FiPackage size={18} />
            </div>
            <div>
              <h3 className="text-[1.05rem] font-semibold tracking-tight">Active Inventory</h3>
              <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Filter and inspect every SKU.</p>
            </div>
          </div>
          <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] bg-[var(--input-background)] px-2.5 py-1 rounded-full border border-[var(--border)] whitespace-nowrap">
            {totalProducts} SKUs
          </div>
        </div>

        <div className="px-5 py-4 flex flex-col sm:flex-row gap-3 border-b border-[var(--border)]">
          <div className="relative flex-1">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" />
            <input
              type="text"
              placeholder="Search by product name or SKU..."
              className="w-full pl-9 pr-4 py-2 bg-[var(--input-background)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 transition-all"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <select
                className="appearance-none bg-[var(--input-background)] border border-[var(--border)] py-2 pl-3 pr-9 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 cursor-pointer"
                value={category}
                onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              >
                <option value="All">All Categories</option>
                <option value="SALES">Sales</option>
                <option value="INVENTORY">Inventory</option>
                <option value="GENERAL">General</option>
                <option value="Electronics">Electronics</option>
                <option value="Furniture">Furniture</option>
                <option value="Lighting">Lighting</option>
                <option value="Accessories">Accessories</option>
              </select>
              <FiFilter className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none" size={14} />
            </div>
            <div className="relative">
              <select
                className="appearance-none bg-[var(--input-background)] border border-[var(--border)] py-2 pl-3 pr-9 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30 cursor-pointer"
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              >
                <option value="All">All Statuses</option>
                <option value="OK">Healthy (OK)</option>
                <option value="LOW">Low Stock</option>
                <option value="OUT">Out of Stock</option>
              </select>
              <FiFilter className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none" size={14} />
            </div>
          </div>
        </div>

        {loadingProducts ? (
          <p className="px-5 py-8 text-sm text-[var(--muted-foreground)]">Loading products…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--input-background)]">
                  {['Product', 'Category', 'Stock', 'Min Stock', 'Health'].map(h => (
                    <th key={h} className="text-left px-5 py-2.5 text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {products.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-[var(--muted-foreground)]">
                      No products found matching the criteria.
                    </td>
                  </tr>
                ) : (
                  products.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => setSelectedProduct(p)}
                      className="group border-t border-[var(--border)] hover:bg-[var(--input-background)] cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-3">
                        <p className="font-semibold group-hover:text-[var(--primary)] transition-colors">{p.name}</p>
                        <p className="text-xs text-[var(--muted-foreground)] font-mono mt-0.5">{p.sku}</p>
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--input-background)] text-[var(--muted-foreground)] text-[11px] font-medium border border-[var(--border)]">
                          {p.category}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <span className="font-semibold">{p.stock_count}</span>
                      </td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">{p.min_stock}</td>
                      <td className="px-5 py-3">
                        <StatusBadge status={p.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {!loadingProducts && products.length > 0 && (
          <div className="px-5 py-3.5 border-t border-[var(--border)] bg-[var(--input-background)] flex items-center justify-between">
            <span className="text-sm text-[var(--muted-foreground)]">
              Showing {(page - 1) * 10 + 1} to {Math.min(page * 10, totalProducts || 0)} of {totalProducts || 0} items
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="px-3 py-1.5 text-sm font-medium border border-[var(--border)] rounded-lg bg-[var(--card)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--input-background)] transition-colors"
              >
                Previous
              </button>
              <button
                disabled={page * 10 >= (totalProducts || 0)}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 text-sm font-medium border border-[var(--border)] rounded-lg bg-[var(--card)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--input-background)] transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>

      <DetailDrawer
        open={!!selectedProduct}
        onClose={() => setSelectedProduct(null)}
        product={selectedProduct}
      />
    </div>
  );
}