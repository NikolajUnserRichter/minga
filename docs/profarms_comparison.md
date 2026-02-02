# Comparison: Profarms Software vs. Minga Greens ERP

**Date:** 2026-02-02  
**Source:** Profarms Vertical Farming System PDF (A31.8.23)

---

## ✅ Features Your ERP Already Has

| Profarms Feature | Minga Greens ERP Equivalent |
|------------------|-----------------------------|
| **Customer Management** | `Customer` model with addresses, price lists |
| **Order Management** | `Order`, `OrderLine` models |
| **Price Lists per Customer** | `PriceList`, `PriceListItem` models with tiered pricing |
| **Invoice & Delivery Note PDF** | `pdf_service.py`, `invoice_service.py` |
| **Inventory/Warehouse Management** | `SeedInventory`, `PackagingInventory`, `FinishedGoodsInventory`, `InventoryLocation` |
| **Seed Variety Management** | `Seed`, `SeedBatch` models with germination/growth parameters |
| **Production Planning** | `GrowBatch`, `GrowPlan`, `ProductionSuggestion` models |
| **Traceability (Seed → Harvest)** | Full chain via `SeedBatch` → `GrowBatch` → `Harvest` → `FinishedGoodsInventory` |
| **Low Stock Warnings** | `needs_reorder()`, `WarningType.SAATGUT_NIEDRIG` |
| **Demand Forecasting** | `Forecast`, `ForecastAccuracy` with Prophet/ARIMA/Ensemble models |
| **Sales Analytics/Dashboard** | `Analytics.tsx`, `Dashboard.tsx` pages |
| **Subscription/Standing Orders** | `Abonnements.tsx` page |

---

## ❌ Features Missing in Your ERP (from Profarms)

| Profarms Feature | Description | Priority |
|------------------|-------------|----------|
| **Hardware/Sensor Integration** | Profarms controls grow racks via software (light, irrigation, ventilation, climate) and reads sensor data (temperature, humidity, CO2, water level) | High |
| **Wachstumsprogramme (Growth Programs)** | Library of automated growth programs per seed variety + batch, adjusting parameters automatically | High |
| **Per-Etage/Tier Control** | Each shelf/tier can run different programs independently | Medium |
| **Germination Chamber (Keimzelle) Management** | Specialized control for germination phase with steam/humidity | Medium |
| **Climate Cell Control** | Temperature, humidity, CO2 management per grow zone | Medium |
| **Irrigation System Control** | Ebb-flow timing, water level, flooding height per shelf | Medium |
| **LED Lighting Control** | Light spectrum, intensity, timing per tier | Medium |
| **Batch-Specific Parameter Adjustment** | Each seed batch gets unique parameters based on quality tests | High |
| **Seed Quality Tests Tracking** | Microbial load, pesticide residue, thousand-kernel weight, germination rate per batch | High |
| **Substrate Parameter Tracking** | Water retention, quality tests per substrate batch | Low |
| **Packaging/Shelf-Life Optimization** | Specialized packaging tracking for microgreens shelf life | Low |
| **Transportwagen (Cart) Logistics** | Tracking plants across carts between germination → grow → storage cells | Low |

---

## 📋 Summary

**Minga Greens ERP** is a solid **business/ERP system** covering:
- Customers, orders, invoices, subscriptions
- Inventory (seeds, packaging, finished goods)
- Production planning & traceability
- Forecasting & analytics

**Profarms Software** is focused on **farm automation**:
- Direct hardware control (racks, irrigation, climate, lighting)
- Sensor data collection & monitoring
- Automated growth programs per variety/batch
- IoT integration for vertical farming equipment

---

## 🚀 Recommended Additions (Priority Order)

1. **Seed Batch Quality Parameters**
   - Add fields to `SeedBatch`: germination_rate, microbial_load_tested, pesticide_tested, thousand_kernel_weight
   - Track quality test results per batch

2. **Growth Program Library**
   - New model: `GrowthProgram` with configurable parameters (light, irrigation, temperature targets)
   - Link to `Seed` varieties with default programs

3. **Sensor Data Collection**
   - New models: `SensorDevice`, `SensorReading`
   - Track temperature, humidity, CO2 per grow zone/location
   - Dashboard widgets for real-time monitoring

4. **Climate Zone Management**
   - Extend `InventoryLocation` with climate parameters
   - Differentiate between germination cells, grow cells, storage cells
