import re

app_file = r"c:\Users\Shreeya S\OneDrive\Desktop\SIH INTERNAL HACKATHON\backend\static\app.html"

with open(app_file, "r", encoding="utf-8") as f:
    content = f.read()

sources_section_html = """
<!-- ===================== DATA SOURCES & BENCHMARK REFERENCES ===================== -->
<div class="content-container" id="dataSourcesSection" style="margin-top:28px;margin-bottom:28px;">
  <div style="background:#FFF;border:1px solid var(--steel-border);border-radius:var(--radius-lg);padding:24px 28px;box-shadow:var(--shadow-sm);">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px;margin-bottom:20px;border-bottom:1px solid var(--steel-border);padding-bottom:16px;">
      <div>
        <div style="display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:0.06em;color:var(--saffron-dark);background:var(--saffron-bg);padding:3px 10px;border-radius:20px;border:1px solid var(--saffron-border);margin-bottom:6px;text-transform:uppercase;">
          📚 Data Governance &amp; Provenance
        </div>
        <h3 style="margin:0;font-size:19px;font-family:'Space Grotesk';color:var(--navy-deep);">Data Sources, Methodology &amp; Benchmark References</h3>
        <p style="margin:4px 0 0;font-size:12.5px;color:var(--steel-muted);">Comprehensive disclosure of all benchmark indices, maritime regulatory standards, port tariffs, and synthetic simulation models used across LOHA-DRISHTI.</p>
      </div>
      <div style="display:flex;gap:8px;">
        <span style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;background:var(--green-bg);color:var(--green);border:1px solid var(--green-border);">✓ 4 PUBLIC BENCHMARKS</span>
        <span style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-border);">⚙ 2 CALIBRATED BASELINES</span>
        <span style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;background:var(--saffron-bg);color:var(--saffron-dark);border:1px solid var(--saffron-border);">⚡ SYNTHETIC STRESS TESTS</span>
      </div>
    </div>

    <!-- 3 PILLARS GRID -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:18px;margin-bottom:24px;">
      <!-- CARD 1 -->
      <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:10px;padding:18px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
          <span style="font-size:16px;">🌐</span>
          <h4 style="margin:0;font-size:14px;color:var(--navy-deep);font-family:'Space Grotesk';">1. Public &amp; Regulatory Benchmarks</h4>
          <span style="margin-left:auto;font-size:10px;font-weight:700;background:var(--green-bg);color:var(--green);padding:2px 8px;border-radius:10px;border:1px solid var(--green-border);">REAL / PUBLIC</span>
        </div>
        <ul style="font-size:12px;color:var(--steel-dark);line-height:1.65;padding-left:18px;margin:0;">
          <li><b>Baltic Dry Index (BDI / C5 Capesize):</b> Real-world dry-bulk freight benchmark standards published by the Baltic Exchange.</li>
          <li><b>Major Port Scale of Rates (SOR):</b> Vessel handling charges, berth hire, and pilotage from the Tariff Authority for Major Ports (TAMP) / Indian Ports Association (IPA).</li>
          <li><b>Admiralty Maritime Distance Tables:</b> Nautical mile (nm) distances and coordinates published by the International Hydrographic Organization (IHO) and NGA.</li>
          <li><b>Indian Railways FOIS Freight Circulars:</b> Distance-based rail freight tariff tables for coking coal and iron ore evacuation to SAIL steel plants.</li>
        </ul>
      </div>

      <!-- CARD 2 -->
      <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:10px;padding:18px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
          <span style="font-size:16px;">📊</span>
          <h4 style="margin:0;font-size:14px;color:var(--navy-deep);font-family:'Space Grotesk';">2. Calibrated Industry Baselines</h4>
          <span style="margin-left:auto;font-size:10px;font-weight:700;background:var(--blue-bg);color:var(--blue);padding:2px 8px;border-radius:10px;border:1px solid var(--blue-border);">CALIBRATED</span>
        </div>
        <ul style="font-size:12px;color:var(--steel-dark);line-height:1.65;padding-left:18px;margin:0;">
          <li><b>FOB Coking Coal Benchmark Prices:</b> Historical commodity price corridors derived from S&amp;P Global Platts and Argus Media ($240–$285/MT).</li>
          <li><b>Marine Fuel Prices (0.5% VLSFO):</b> Bunkering spot prices benchmarked against Singapore and Fujairah bunkering ports ($580–$660/MT).</li>
          <li><b>Vessel Specifications &amp; Drafts:</b> Standard naval architecture dimensions for Handysize, Supramax, Panamax, and Capesize bulk carriers.</li>
          <li><b>Seasonal Monsoon Delay Factors:</b> Historical meteorological downtime distributions for Bay of Bengal ports (June–September).</li>
        </ul>
      </div>

      <!-- CARD 3 -->
      <div style="background:var(--bg-subtle);border:1px solid var(--steel-border);border-radius:10px;padding:18px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
          <span style="font-size:16px;">🧪</span>
          <h4 style="margin:0;font-size:14px;color:var(--navy-deep);font-family:'Space Grotesk';">3. Synthetic &amp; Stress Simulation</h4>
          <span style="margin-left:auto;font-size:10px;font-weight:700;background:var(--saffron-bg);color:var(--saffron-dark);padding:2px 8px;border-radius:10px;border:1px solid var(--saffron-border);">SIMULATED</span>
        </div>
        <ul style="font-size:12px;color:var(--steel-dark);line-height:1.65;padding-left:18px;margin:0;">
          <li><b>Demo Requisition Parcels:</b> Simulated SAIL procurement batches (25,000–180,000 MT) for Rourkela, Bhilai, Durgapur, Bokaro, and Burnpur.</li>
          <li><b>Disruption Injection Matrix:</b> Synthetic scenario testing for Cyclone Warnings (Odisha Coast), Primary Port Closures, and Freight Spikes (+20%).</li>
          <li><b>Minimax-Regret Score Engine:</b> Multi-scenario cost and supply continuity optimizer designed for automated decision resilience.</li>
          <li><b>ML Gradient Boosting Regressor:</b> Trained on 1,500 calibrated voyage records with 8 feature encodings ($R^2 = 0.9891$).</li>
        </ul>
      </div>
    </div>

    <!-- REFERENCE TABLE -->
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;text-align:left;font-size:12px;">
        <thead>
          <tr style="background:var(--bg-subtle);border-bottom:2px solid var(--steel-border);">
            <th style="padding:10px 12px;font-weight:700;color:var(--navy-deep);font-family:'Space Grotesk';">Dataset / Metric</th>
            <th style="padding:10px 12px;font-weight:700;color:var(--navy-deep);font-family:'Space Grotesk';">Primary Reference Authority</th>
            <th style="padding:10px 12px;font-weight:700;color:var(--navy-deep);font-family:'Space Grotesk';">Data Classification</th>
            <th style="padding:10px 12px;font-weight:700;color:var(--navy-deep);font-family:'Space Grotesk';">Frequency / Baseline</th>
            <th style="padding:10px 12px;font-weight:700;color:var(--navy-deep);font-family:'Space Grotesk';">System Application</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom:1px solid var(--steel-border);">
            <td style="padding:10px 12px;"><b>Baltic Capesize Index (C5 / C3)</b></td>
            <td style="padding:10px 12px;">Baltic Exchange / S&amp;P Global Commodity Insights</td>
            <td style="padding:10px 12px;"><span style="background:var(--green-bg);color:var(--green);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10.5px;">Public Benchmark</span></td>
            <td style="padding:10px 12px;color:var(--steel-muted);">Daily Market Index</td>
            <td style="padding:10px 12px;">Freight Forecasting &amp; P10/P50/P90 Confidence Bands</td>
          </tr>
          <tr style="border-bottom:1px solid var(--steel-border);">
            <td style="padding:10px 12px;"><b>Indian Major Ports Draft &amp; Tariff</b></td>
            <td style="padding:10px 12px;">Ministry of Ports, Shipping and Waterways / IPA</td>
            <td style="padding:10px 12px;"><span style="background:var(--green-bg);color:var(--green);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10.5px;">Regulatory Tariff</span></td>
            <td style="padding:10px 12px;color:var(--steel-muted);">Statutory SOR 2024–26</td>
            <td style="padding:10px 12px;">Port Compatibility, Berth Charges &amp; Demurrage Calculations</td>
          </tr>
          <tr style="border-bottom:1px solid var(--steel-border);">
            <td style="padding:10px 12px;"><b>Nautical Distances &amp; Waypoints</b></td>
            <td style="padding:10px 12px;">Admiralty Maritime Distance Tables / IHO</td>
            <td style="padding:10px 12px;"><span style="background:var(--green-bg);color:var(--green);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10.5px;">Standard Reference</span></td>
            <td style="padding:10px 12px;color:var(--steel-muted);">Static Distance Matrix</td>
            <td style="padding:10px 12px;">Interactive Map Route Paths &amp; Voyage Transit Days</td>
          </tr>
          <tr style="border-bottom:1px solid var(--steel-border);">
            <td style="padding:10px 12px;"><b>Indian Railways Steel Plant Tariffs</b></td>
            <td style="padding:10px 12px;">Railway Board / FOIS (Freight Operations Information System)</td>
            <td style="padding:10px 12px;"><span style="background:var(--blue-bg);color:var(--blue);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10.5px;">Calibrated Model</span></td>
            <td style="padding:10px 12px;color:var(--steel-muted);">Trainload Class 140 / 150</td>
            <td style="padding:10px 12px;">Inland Evacuation &amp; Total Landed Cost (TLC) Computation</td>
          </tr>
          <tr>
            <td style="padding:10px 12px;"><b>SAIL Requisition &amp; Disruption Scenarios</b></td>
            <td style="padding:10px 12px;">LOHA-DRISHTI Simulation Engine (SIH PS 26006)</td>
            <td style="padding:10px 12px;"><span style="background:var(--saffron-bg);color:var(--saffron-dark);padding:2px 8px;border-radius:10px;font-weight:700;font-size:10.5px;">Synthetic / Demo</span></td>
            <td style="padding:10px 12px;color:var(--steel-muted);">Parameterized Generator</td>
            <td style="padding:10px 12px;">Interactive Hackathon Demonstrator &amp; What-If Engine</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>
"""

# Insert before <footer>
if "<!-- ===================== DATA SOURCES & BENCHMARK REFERENCES ===================== -->" not in content:
    content = content.replace("<footer>", sources_section_html + "\n<footer>")
    print("Data sources & benchmark references section added above footer.")

with open(app_file, "w", encoding="utf-8") as f:
    f.write(content)
print("app.html updated successfully.")
