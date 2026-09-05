import React, { useState } from 'react';

export default function Dashboard({ onLogout }) {
  const [activePanel, setActivePanel] = useState('command');

  const handleEmergencyLanding = () => {
    alert(
      'Emergency Landing Activated!\n\nVessel diverted to temporary safe port.\nCargo remains protected until the optimal route is restored.'
    );
  };

  return (
    <div>
      {/* ================= TOP BAR ================= */}
      <div className="topbar">
        <div className="brand">
          <img
            className="brand-mark"
            src="/loha-drishti-logo.svg"
            alt="Loha Drishti maritime emblem"
          />

          <div>
            <div className="brand-text">LOHA DRISHTI</div>
            <div className="brand-sub">
              Maritime Decision Intelligence · SAIL Logistics
            </div>
          </div>
        </div>

        <div className="nav-menu">
          <a
            className={activePanel === 'command' ? 'active' : ''}
            onClick={() => setActivePanel('command')}
          >
            ⚙ Command Center
          </a>

          <a
            className={activePanel === 'intelligence' ? 'active' : ''}
            onClick={() => setActivePanel('intelligence')}
          >
            📊 Intelligence
          </a>

          <a
            className={activePanel === 'scenarios' ? 'active' : ''}
            onClick={() => setActivePanel('scenarios')}
          >
            ⚡ Scenarios
          </a>

          <a
            className={activePanel === 'transparency' ? 'active' : ''}
            onClick={() => setActivePanel('transparency')}
          >
            📖 Data Sources
          </a>
        </div>

        <div className="topbar-actions">
          <button className="icon-btn" onClick={onLogout}>
            🚪 Logout
          </button>
        </div>
      </div>

      {/* ================= CARGO BAR ================= */}
      <div className="cargo-bar-wrapper">
        <div className="cargo-bar">
          <div className="cargo-summary-pills">
            <div className="cargo-pill">
              <span className="label">Parcel:</span>{' '}
              <span>80,000 MT</span>
            </div>

            <div className="cargo-pill">
              <span className="label">Cargo:</span>{' '}
              <span>Coking Coal</span>
            </div>

            <div className="cargo-pill">
              <span className="label">Origin:</span>{' '}
              <span>Australia</span>
            </div>
          </div>

          <div className="cargo-actions">
            <button className="btn-optimize">
              ⚡ FIND BEST STRATEGY
            </button>
          </div>
        </div>
      </div>

      {/* ================= SECTION TABS ================= */}
      <div className="section-tabs">
        <button
          className={`tab-btn ${
            activePanel === 'command' ? 'active' : ''
          }`}
          onClick={() => setActivePanel('command')}
        >
          Command Center
        </button>

        <button
          className={`tab-btn ${
            activePanel === 'intelligence' ? 'active' : ''
          }`}
          onClick={() => setActivePanel('intelligence')}
        >
          Freight Intelligence
        </button>

        <button
          className={`tab-btn ${
            activePanel === 'transparency' ? 'active' : ''
          }`}
          onClick={() => setActivePanel('transparency')}
        >
          Data & Methodology
        </button>
      </div>

      {/* =====================================================
          COMMAND CENTER
         ===================================================== */}

      {activePanel === 'command' && (
        <div className="panel active">
          <div className="section">

            <div className="section-header">
              <div>
                <h2>
                  Executive Command Center — WHAT SHOULD I DO?
                </h2>

                <p>
                  Primary strategy recommendation based on
                  Minimax-Regret optimization across market scenarios.
                </p>
              </div>

              <span className="section-tag">
                Recommended Strategy
              </span>
            </div>

            {/* EXISTING STRATEGY BOX */}
            <div
              style={{
                textAlign: 'center',
                padding: '50px 20px',
                background: 'var(--bg-surface)',
                border: '1px dashed var(--steel-border)',
                borderRadius: 'var(--radius-lg)'
              }}
            >
              <div
                style={{
                  fontSize: '32px',
                  marginBottom: '10px'
                }}
              >
                ⚡
              </div>

              <div
                style={{
                  fontFamily: "'Space Grotesk'",
                  fontSize: '18px',
                  fontWeight: '700',
                  color: 'var(--navy-deep)'
                }}
              >
                Click FIND BEST STRATEGY to begin
              </div>

              <div
                style={{
                  fontSize: '13px',
                  color: 'var(--steel-muted)',
                  marginTop: '6px'
                }}
              >
                The decision engine will evaluate all
                origin-port-vessel combinations.
              </div>
            </div>


            {/* =================================================
                🛟 EMERGENCY LANDING — TEMPORARY PORT
               ================================================= */}

            <div
              style={{
                marginTop: '24px',
                padding: '24px',
                borderRadius: '18px',
                background:
                  'linear-gradient(135deg, #111827, #1f2937)',
                border:
                  '1px solid rgba(255,255,255,0.12)',
                color: '#ffffff',
                boxShadow:
                  '0 10px 30px rgba(0,0,0,0.15)'
              }}
            >

              {/* HEADER */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: '15px'
                }}
              >

                <div>
                  <div
                    style={{
                      fontSize: '10px',
                      fontWeight: '800',
                      letterSpacing: '1.5px',
                      opacity: 0.55
                    }}
                  >
                    EMERGENCY RESPONSE
                  </div>

                  <h2
                    style={{
                      margin: '6px 0 0',
                      fontSize: '21px'
                    }}
                  >
                    🛟 Emergency Landing
                  </h2>
                </div>

                <span
                  style={{
                    padding: '6px 10px',
                    borderRadius: '20px',
                    background:
                      'rgba(34,197,94,0.14)',
                    color: '#4ade80',
                    fontSize: '11px',
                    fontWeight: '800'
                  }}
                >
                  ● SAFE-HOLD
                </span>

              </div>


              {/* DESCRIPTION */}

              <p
                style={{
                  margin: '12px 0 20px',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  opacity: 0.7
                }}
              >
                Primary port becomes unavailable due to a
                disruption. LOHA-DRISHTI recommends a temporary
                safe port to protect cargo continuity.
              </p>


              {/* INFORMATION BOXES */}

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'repeat(4, 1fr)',
                  gap: '12px'
                }}
              >

                {/* VESSEL */}

                <div
                  style={{
                    padding: '14px',
                    borderRadius: '12px',
                    background:
                      'rgba(255,255,255,0.06)'
                  }}
                >
                  <div
                    style={{
                      fontSize: '11px',
                      opacity: 0.55,
                      marginBottom: '7px'
                    }}
                  >
                    🚢 CURRENT VESSEL
                  </div>

                  <strong>
                    MV LOHA-01
                  </strong>
                </div>


                {/* PRIMARY PORT */}

                <div
                  style={{
                    padding: '14px',
                    borderRadius: '12px',
                    background:
                      'rgba(255,255,255,0.06)'
                  }}
                >
                  <div
                    style={{
                      fontSize: '11px',
                      opacity: 0.55,
                      marginBottom: '7px'
                    }}
                  >
                    🚫 PRIMARY PORT
                  </div>

                  <strong>
                    PORT DISRUPTED
                  </strong>
                </div>


                {/* TEMPORARY PORT */}

                <div
                  style={{
                    padding: '14px',
                    borderRadius: '12px',
                    background:
                      'rgba(255,255,255,0.06)'
                  }}
                >
                  <div
                    style={{
                      fontSize: '11px',
                      opacity: 0.55,
                      marginBottom: '7px'
                    }}
                  >
                    📍 TEMPORARY PORT
                  </div>

                  <strong>
                    ALTERNATIVE SAFE PORT
                  </strong>
                </div>


                {/* CARGO */}

                <div
                  style={{
                    padding: '14px',
                    borderRadius: '12px',
                    background:
                      'rgba(255,255,255,0.06)'
                  }}
                >
                  <div
                    style={{
                      fontSize: '11px',
                      opacity: 0.55,
                      marginBottom: '7px'
                    }}
                  >
                    📦 CARGO PROTECTED
                  </div>

                  <strong>
                    80,000 MT
                  </strong>
                </div>

              </div>


              {/* FOOTER */}

              <div
                style={{
                  marginTop: '20px',
                  paddingTop: '16px',
                  borderTop:
                    '1px solid rgba(255,255,255,0.1)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '15px'
                }}
              >

                <span
                  style={{
                    fontSize: '12px',
                    color: '#86efac'
                  }}
                >
                  ✓ Cargo protected until alternate route
                  is available
                </span>


                <button
                  onClick={handleEmergencyLanding}
                  style={{
                    border: 'none',
                    padding: '11px 17px',
                    borderRadius: '10px',
                    background: '#f59e0b',
                    color: '#111827',
                    fontWeight: '800',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  DIVERT TO TEMPORARY PORT →
                </button>

              </div>

            </div>

          </div>
        </div>
      )}


      {/* =====================================================
          INTELLIGENCE
         ===================================================== */}

      {activePanel === 'intelligence' && (
        <div className="panel active">
          <div className="section">

            <div className="section-header">
              <div>
                <h2>
                  Freight Intelligence & Market Pressure
                </h2>

                <p>
                  Historical trends and market timing signals.
                </p>
              </div>
            </div>

            <div className="chart-card">
              <h4
                style={{
                  margin: '0',
                  fontSize: '14px'
                }}
              >
                Data will load from API...
              </h4>
            </div>

          </div>
        </div>
      )}


      {/* =====================================================
          TRANSPARENCY
         ===================================================== */}

      {activePanel === 'transparency' && (
        <div className="panel active">
          <div className="section">

            <div className="section-header">
              <div>
                <h2>
                  Data Sources & Methodology
                </h2>

                <p>
                  Transparent documentation of all datasets
                  and models used in the platform.
                </p>
              </div>
            </div>

            <div className="decision-card">

              <h3>Datasets</h3>

              <ul>

                <li>
                  <strong>
                    Freight and Shipping Data:
                  </strong>{' '}
                  Simulated based on general historical
                  Baltic Dry Index (BDI) and bunker fuel
                  prices to mimic realistic market conditions
                  (Synthetic Benchmark Data).
                </li>

                <li>
                  <strong>
                    Port Data:
                  </strong>{' '}
                  Real publicly available parameters
                  (max draft, LOA, loading rates) for major
                  Indian ports like Paradip, Dhamra, Haldia,
                  and Vizag (Real Public Data).
                </li>

                <li>
                  <strong>
                    Vessel Data:
                  </strong>{' '}
                  Standardized maritime industry averages
                  for Panamax, Supramax, and Capesize classes
                  (Real Industry Standard Data).
                </li>

                <li>
                  <strong>
                    Commodity/Cargo Data:
                  </strong>{' '}
                  Coking coal and limestone operational
                  requirements provided by SAIL specifications
                  (Sample Operational Data).
                </li>

              </ul>

              <hr
                style={{
                  margin: '20px 0',
                  borderColor: 'var(--steel-border)',
                  borderStyle: 'solid'
                }}
              />

              <h3>
                Machine Learning Methodology
              </h3>

              <p>
                The platform utilizes a{' '}
                <strong>
                  Random Forest Regressor
                </strong>{' '}
                (Scikit-Learn) to forecast freight rates.
                It is trained on historical features including
                Route Distance, Month (Seasonality), Bunker
                Fuel Price, and Market Pressure Indices.
                The model achieves an average Mean Absolute
                Error (MAE) of $2.30/MT and an R2 Score of
                ~0.95 on the simulated dataset.
              </p>

            </div>

          </div>
        </div>
      )}

    </div>
  );
}
