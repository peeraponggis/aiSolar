# PVsyst Knowledge Base - Comprehensive Training Data
# Source: Facebook Community Posts (titles/descriptions) + PVsyst Official Documentation
# Generated: 2026-09-19
# Total Topics: 41 (PVsyst Version 8 Features, Tutorials, and Design Guidelines)

========================================
SECTION 1: PVsyst Version 8 - Major Changes
========================================

[TOPIC 1] PVsyst Version 8 - New Features Overview
Release: November 07, 2024
Version History: 8.0.0 → 8.0.1 → 8.0.2 → 8.0.3 → 8.0.4 → 8.0.7 → 8.0.8 → ... → 8.0.21 (Mar 2026) → 8.1.0 (Apr 2026) → 8.1.1 → 8.1.2 → 8.1.3 → 8.1.4 (Jun 2026) → 8.1.5 (Aug 2026)

Key Changes from Version 7:
1. **Orientation Management (Major Change)**
   - PVsyst 7: Single uniform orientation for entire project (limited multi-orientation)
   - PVsyst 8: Unlimited orientations per system - each orientation is independent
   - Can combine fixed + tracking arrays in single simulation
   - All sub-arrays and 3D tables can have different orientations
   - Bifacial performance simulated independently per orientation

2. **System Sizing Flexibility**
   - Visual sizing constraints for modules and inverters
   - I/V curves and power distribution visualization
   - Optimal inverter sizing with comprehensive loss analysis

3. **Sub-hourly Simulation**
   - Import meteorological data at sub-hourly intervals from Meteonorm 9
   - Greater accuracy in energy production simulation

4. **3D Scene Tools**
   - Model 3D scene directly or import from CAD tools
   - Fast design tools, orientation identification
   - Scene validation and advanced multithreading calculations

5. **Shading Analysis**
   - Near shadings: 3D modeling with precise electrical shading losses
   - Horizon: Distant shadows from sun positions (import from Meteonorm/PVGIS)
   - Layout: I/V characteristics calculation per string

6. **Meteorological Databases**
   - Bing/OpenStreetMaps for project location
   - Supports: Meteonorm 8.2/9, NASA-SSE, PVGIS-TMY, NREL/NSRDB, Solcast, Solar Anywhere, Solargis
   - Many formats importable manually

7. **Advanced Tools**
   - Ageing, optimization, batch processing
   - Multi-year batch simulation
   - PV module ageing simulation

8. **Economic Assessment**
   - CAPEX, OPEX, custom costs
   - NPV, LCOE, ROI calculations

9. **UI Improvements**
   - Light/dark modes
   - Improved search engine (mkDocs)
   - Table of contents navigation
   - Better readability

205 Differences between V7 and V8 (Nov 2024 - Apr 2025):
- Orientation: from limited to unlimited
- 3D scene: enhanced tools
- Shading: more precise calculations
- Simulation: sub-hourly support added
- Database: updated components
- UI: modernized interface

[TOPIC 3] PVsyst 8.1 Features (Apr 2026)
- New assistant for Weather Data import
- Sub-hourly Simulation for Grid-Connected and Standalone systems
- Meteonorm updated to DLL V9 (replacing V8.2)
- Bifacial 3D modeling
- Expanded AC circuit
- New batch mode features
- Enhanced weather data import interface

[TOPIC 18] PVsyst Version 8 Complete Guide
- Full manual available for Grid Connected Systems, My First Project
- Comprehensive documentation using mkDocs technology
- Video tutorials available on PVsyst channels

========================================
SECTION 2: PVsyst .PAN File Management
========================================

[TOPIC 4] Creating .PAN File from Datasheet
.PAN = Panel (Panneau Solaire) - PVsyst native module format

Step-by-step Process:
1. Click "Databases" button under Utilities
2. Click "PV modules" under components database
3. Define new module from datasheet:
   - Data source (and date of recording)
   - File name (primary key): Convention = "Manufacturer_Model.PAN"
4. Complete Manufacturer Specifications:
   - STC ratings (Voc, Isc, Vmp, Imp, Pmax)
   - Temperature coefficients
   - Show optimization button: modify parameters, see real-time effect
   - Copy to table button: export to Excel

Key Points:
- Easier to start from existing similar component → modify → save as new file
- PAN files are text-based, exchangeable between programs
- Can also create .OND files for inverters (similar process)
- Alternative tools: PV Ivy (pan builder), PVhub (AI PAN generator)
- .PAN contains single-diode model parameters (Isc, Voc, Imp, Vmp, Gamma, Rs, Rsh)

[TOPIC 33] String Configuration with Huawei Optimizer (C&I)
- Design string configuration using optimizer modules
- Huawei optimizer integration in PVsyst
- For Commercial & Industrial (C&I) applications

[TOPIC 34] String Configuration with SolarEdge Inverter
- Design string configuration specifically for SolarEdge
- Inverter sizing and string layout
- Power sharing and MPPT configuration

========================================
SECTION 3: Loss Analysis & Shading
========================================

[TOPIC 5] Detailed Losses (Before Simulation)
Access: "Detailed losses" button in project dashboard
Parameters to set before simulation:
- Thermal loss coefficient (Uc): 20 W/m²K (semi-integrated), 15 W/m²K (integrated)
- DC wiring losses (global array resistance, % at STC)
- Module Quality Loss (%)
- Module Mismatch Losses (at MPP, %)
- Ohmic losses (Ploss = R × I²)
- IAM factor (Incidence Angle Modifier)
- Soiling Loss (%)
- LID (Light Induced Degradation) (%)

Key Concept: Each loss is % of previous energy quantity - NOT additive!

[TOPIC 6] Loss Diagram (After Simulation)
What it shows:
- Energy distribution from irradiation input to AC output
- Visual breakdown of all system losses
- Annual summary + monthly detail

Loss structure:
1. Global Horizontal Irradiation (GHI)
2. + Global incident in collector plane (+IAM)
3. - Near Shadings: irradiance loss
4. - Far Shadings / Horizon
5. - Module mismatch losses
6. - DC wiring losses
7. - Thermal losses
8. - Module quality loss
9. - Soiling loss
10. = Effective AC energy output

[TOPIC 7] Detailed Loss Diagram (Deep Dive)
Loss types in PVsyst:
- Linear shading losses (Beam, Circumsolar, Diffuse, Albedo)
- Electrical shading losses (ShdElec) - bypass diode activation
- 3 calculation methods for electrical shading:
  1. Simple fraction
  2. Module Layout (most accurate - I/V curve combinations)
  3. Partition approximation (faster, regular rows)

[TOPIC 8] PVsyst Tutorial: Detailed Losses
Purpose: Understand where energy is lost in system
Use: Optimize system design by minimizing key losses
Typical loss ranges:
- Soiling: 2-7%
- Thermal: 5-15%
- Module mismatch: 1-2%
- DC wiring: 1-2%
- IAM: 2-8%
- Shading: varies greatly by site

[TOPIC 40] Module String vs Module Layout Shading
Two methods for shading calculation:
1. **Module String**: Based on string-level electrical behavior
   - Faster calculation
   - Conservative estimates
   - Good for preliminary design

2. **Module Layout**: Based on individual module placement
   - More accurate
   - Considers exact module positions in 3D scene
   - Combines I/V curves of all components
   - Recommended for final design

Difference: Module Layout shows more precise electrical mismatch losses from shading geometry

========================================
SECTION 4: Bifacial Systems
========================================

[TOPIC 9] Bifacial Systems Results
Key concepts:
- Front-side irradiance (standard PV)
- Rear-side irradiance (bifacial gain)
- Bifaciality factor (φ) = rear efficiency / front efficiency

PVsyst 8 improvements for bifacial:
- Independent orientations per subsystem
- More flexible bifacial modeling
- Bifacial 3D modeling (v8.1)
- Bifacial Performance Ratio (PR_Bifi) calculated in PVsyst 8.0.12+

Results include:
- Bifacial gain percentage
- Rear irradiance distribution
- Shading from structure on rear side
- Optimal height/row spacing for max rear irradiance

[TOPIC 37] Ground Coverage Ratio (GCR)
GCR = (Module area) / (Total ground area)
- Important for spacing between rows
- Lower GCR = more spacing = less inter-row shading but more land use
- Typical: 20-40% for ground-mounted
- Affects: inter-row shading, soil loss, maintenance access

Design considerations:
- Higher GCR → more land efficient, more shading risk
- Lower GCR → less efficient, less shading, easier maintenance
- Affects tracker backtracking limits

[TOPIC 24] Ground Mounted Tracking System vs Fixed System
- **Fixed**: Single tilt/azimuth, simpler, lower cost
- **Tracking**: Single-axis or dual-axis, follows sun, higher energy yield
  - Single-axis: ~15-25% gain over fixed
  - Dual-axis: ~30-40% gain over fixed
- **Backtracking**: Feature to avoid row-to-row shading in trackers
  - PVsyst 8: Advanced backtracking algorithms
  - Can combine trackers with fixed in same project (V8+)

========================================
SECTION 5: Shading Analysis
========================================

[TOPIC 11] Iso-shading Diagram
What: Visual tool showing shading impact per orientation
Purpose: Critical for designing complex systems with multiple orientations
Shows:
- Shading fraction at different sun positions
- Per orientation basis
- Helps identify critical shading periods

Why important:
- Multiple orientations need independent shading analysis
- Affects energy yield accuracy
- Required for complex commercial/utility projects

[TOPIC 12] Why Hourly Solar Data Per Location Is Insufficient
Issue: Using only average peak sun hours (PSH) is incorrect because:
- PSH is an average - loses temporal distribution
- Self-consumption depends on timing of production vs usage
- Battery storage depends on daily patterns
- Shading effects vary hour by hour
- System losses are time-dependent

Solution: Use actual hourly/sub-hourly meteorological data
- Meteonorm, PVGIS, NASA-SSE, Solcast, etc.
- PVsyst 8: Sub-hourly simulation support

[TOPIC 35] Near Shading vs Far Shading
**Near Shading**:
- From objects within ~3x module distance
- Modeled with 3D scene (buildings, trees, terrain)
- Calculated from sun position + 3D geometry
- Can import from CAD tools
- Affects: beam, circumsolar, diffuse, albedo components

**Far Shading (Horizon)**:
- From distant objects on horizon
- Defined by sun positions (horizon profile)
- Can import from Meteonorm/PVGIS automatically
- Affects: mainly beam component

[TOPIC 36] Near Shading vs Far Shading (continued)
Key differences:
| Aspect | Near Shading | Far Shading |
|--------|-------------|-------------|
| Distance | < 3x module height | > 3x module height |
| Source | Buildings, terrain, vegetation | Mountains, distant structures |
| Model | 3D scene import | Horizon profile |
| Components | Beam + Diffuse + Albedo | Mainly Beam |
| Import | CAD, manual | Meteonorm, PVGIS auto |

[TOPIC 35] Topology & Far Shading Optimization
When installing near mountains:
- Use "Simplify 3D" for distant objects
- Define far shading objects as simplified shapes
- Balance accuracy vs simulation speed
- Avoid overestimating shading impact
- Focus on critical orientations

========================================
SECTION 6: Solar Irradiation & Meteorological Data
========================================

[TOPIC 13] P50 - P90 Evaluations
**P50**: Median annual energy production (50% probability of exceeding)
**P90**: Conservative estimate (90% probability of exceeding)

Statistical basis:
- Assumes normal (Gaussian) distribution of annual yields
- P50 = 50th percentile = mean (for symmetric distribution)
- P90 = 10th percentile

Key sources of uncertainty:
1. Weather data (largest uncertainty)
2. PV module model/parameters
3. Soiling and module quality loss
4. Degradation rate
5. Custom contributions

Important: P50-P90 only meaningful for ANNUAL yields
- Not valid for sub-hourly, hourly, daily, or monthly
- Common mistake: scaling hourly results by P90/P50 ratio → INCORRECT

Relationship to PR:
- PR = Performance Ratio (overall system efficiency indicator)
- P50/P90 use PR as basis for uncertainty analysis
- PR is independent of yearly irradiation

[TOPIC 14] Capacity Factor & Aging Tool
**Capacity Factor** = Actual output / Maximum possible output
- CF = E_actual / (P_nom × hours)
- Typically 10-30% for solar
- Related to E Grid in Aging Tool

**Aging Tool** (PVsyst):
- Describes performance evolution over years
- Module degradation effects
- Increasing mismatch over time
- Usually -0.5% to -0.75% per year (median)
- Can go faster at P90 value

[TOPIC 28] Degradation Analysis
Methods in PVsyst:
- Annual performance decline rate
- Module degradation (typically 0.5-0.7%/year)
- Increasing electrical mismatch over time
- Availability loss
- Performance Loss Rate (PLR)

========================================
SECTION 7: Design Optimization
========================================

[TOPIC 10] Ground Coverage Ratio (GCR) Design
GCR importance:
- Determines row spacing
- Affects energy yield vs land cost trade-off
- Impacts maintenance access
- Controls inter-row shading

Optimal GCR depends on:
- Latitude (higher lat → lower optimal GCR)
- Terrain (flat vs sloped)
- Module tilt and azimuth
- Tracking vs fixed

[TOPIC 27] Optimization Tools - Tilt & Orientation
Finding optimal tilt/azimuth:
1. Use "Optimization Tools" in PVsyst 8
2. PVsyst calculates optimal tilt/azimuth for maximum yield
3. Consider:
   - Annual production maximization
   - Seasonal distribution
   - Self-consumption timing
   - Grid constraints

Methods:
- Fixed tilt optimization
- Pitch optimization
- Backtracking analysis
- Multi-objective optimization

[TOPIC 25] Project Setting Importance
Project settings are MOST critical in PVsyst because:
- Define baseline for all calculations
- Weather data selection affects all results
- System configuration determines losses
- Economic parameters drive financial analysis
- Wrong settings → wrong conclusions

[TOPIC 26] Site-Dependent Design Parameters
Critical site-specific parameters:
- Location (latitude, longitude)
- Weather data source
- Terrain elevation
- Ambient temperature profile
- Wind speed data
- Local irradiance conditions
- Shading environment

These determine:
- Module operating temperature
- Inverter efficiency
- Cable losses
- Soiling rates
- Overall system yield

[TOPIC 30] Pitch Concept in Solar Farm
Common misconception about "Pitch":
- Pitch = distance between rows (correct)
- Pitch is NOT the same as row spacing in all contexts
- In PVsyst: Pitch affects both front and rear row shading
- Tilt affects effective pitch at ground level

[TOPIC 31] Ground Mounted Fixed vs Domes
"Fixed Tilt" vs "Domes" (or "Dome-shaped"):
- **Fixed Tilt**: Uniform tilt for all rows
  - Simpler design
  - Easier construction
  - May have more shading at edges

- **Dome-shaped**: Varying tilt/height across rows
  - Can reduce mutual shading
  - Better for hilly terrain
  - More complex construction
  - May optimize yield at higher cost

[TOPIC 32] Backtracking for Solar Farm Trackers
Backtracking:
- Tracker adjusts angle to avoid row-to-row shading
- Critical for low GCR installations
- Algorithm: calculates optimal tilt to avoid casting shadow on next row
- PVsyst 8: Advanced backtracking with:
  - Per-row tracking
  - Backtracking limit settings
  - Safety margins
  - Combined with fixed arrays possible (V8+)

========================================
SECTION 8: Financial Analysis
========================================

[TOPIC 29] Key Financial Metrics in PVsyst

**ROI (Return on Investment)** = Net Profit / Total Investment × 100%
- Measures overall profitability
- Affected by: energy price, CAPEX, OPEX, system lifetime

**NPV (Net Present Value)** = Sum of discounted cash flows
- Discount rate (typically 5-10%)
- Positive NPV = profitable project
- Used for project comparison

**IRR (Internal Rate of Return)** = Discount rate making NPV = 0
- Higher than cost of capital = good investment
- Affected by all cash flow parameters

**PBP (Payback Period)** = Time to recover initial investment
- Simple metric for investors
- Can be simple or discounted

**LCOE (Levelized Cost of Energy)** = Total cost / Total energy
- LCOE = (CAPEX + OPEX discounted) / (Energy discounted)
- Compare with grid price/tariff
- Key metric for project viability

**CAPEX (Capital Expenditure)**
- Initial investment costs
- Module, inverter, racking, installation, grid connection
- In PVsyst: "Installation and operating costs" section

**OPEX (Operating Expenditure)**
- Annual operating costs
- Maintenance, insurance, land lease, taxes
- Varies by system size and location

How to calculate in PVsyst:
1. Economic evaluation dialog (after simulation)
2. Define costs (CAPEX, OPEX)
3. Set financial parameters (discount rate, inflation, lifetime)
4. PVsyst calculates all metrics automatically
5. Results: LCOE, ROI, NPV, IRR, PBP

========================================
SECTION 9: System Design Examples
========================================

[TOPIC 15] Solar Farm PVsyst Report (Example)
Typical report includes:
- Project and results summary
- General parameters
- PV Array characteristics
- System losses breakdown
- Loss diagram
- Near shading definition
- Iso-shadings diagram
- Main results
- P50/P90 evaluation
- Single-line diagram
- Monthly/daily yield indicators

[TOPIC 16] Solar Floating Report (192 MWp Example)
Floating PV specifics:
- Module tilt from water surface
- Wind/wave loading considerations
- Water reflection (albedo) = higher gain
- Mooring system effects on shading
- Typical design: 192 MWp example available

[TOPIC 17] Cirata Solar Floating Project (192 MWp, Indonesia)
Design process from Google Maps:
1. Import satellite imagery as base
2. Define water body boundaries
3. Place floating PV arrays
4. Configure electrical connections
5. Run simulation
6. Analyze results

========================================
SECTION 10: PVsyst Software & Tutorials
========================================

[TOPIC 18] PVsyst Version 8 + Software Bundle
Available versions:
- PVsyst 8 (Professional): ~$891 USD/year
- PVsystCLI: Command-line interface for automation
- PVsystBasic: Pumping systems only, ~$25/year
- Free trial: 1-2 months, limited simulations

PVsystCLI features:
- Automated simulation workflows
- Batch processing
- Meteorological data conversion
- Customizable commands
- CSV output for analysis
- Integration with other tools

[TOPIC 19] Grid Connected Systems Manual (Free)
Comprehensive guide covering:
- Project definition and workflow
- 3D scene and shading
- System definition
- Detailed losses
- Results analysis
- Economic evaluation

[TOPIC 20] Grid Connected Design Guide
Design workflow:
1. Project setup (location, weather, project type)
2. Define PV array (modules, inverters, strings)
3. System orientation (tilt, azimuth)
4. Shading analysis (near, far)
5. Detailed losses settings
6. Economic evaluation
7. Simulation and results

[TOPIC 21] Stand Alone (Off-Grid) + Pumping Design
Off-grid system specifics:
- Battery sizing critical
- Self-consumption optimization
- User load profile definition
- System autonomy days

Pumping system specifics:
- Hydraulic analysis
- Pump operating point
- Well characterization
- Water demand management

[TOPIC 22] 3D Scene Export Procedures
Export process:
1. Design 3D scene in PVsyst or CAD
2. Export to standard format
3. Import into PVsyst
4. Validate scene
5. Run shading calculations

[TOPIC 38] Pumping System Tutorial (Free)
Step-by-step:
1. System type selection (pumping)
2. Define water source (well, tank, etc.)
3. Pump selection
4. Pipe sizing
5. Daily operating schedule
6. PV array sizing
7. Simulation

[TOPIC 39] Standalone System Tutorial (Free)
Step-by-step:
1. Load profile definition
2. Battery selection
3. PV array sizing
4. Controller configuration
5. Seasonal variation analysis
6. Autonomy verification

========================================
SECTION 11: Design Errors & Warnings
========================================

[TOPIC 23] 10+1 Design Failure Factors
Common PVsyst design errors:
1. Wrong weather data selection
2. Incorrect module/inverter matching
3. Missing shading analysis
4. Unrealistic loss assumptions
5. Wrong system orientation
6. Ignoring temperature effects
7. Improper inverter sizing
8. Wrong GCR/pitch settings
9. Not using detailed losses
10. Ignoring economic assumptions
11. Not validating results with sensitivity analysis

[TOPIC 41] Professional Solar Presentation
Tips for professional presentations:
- Clear project summary
- Visual 3D scene
- Loss diagram (key chart)
- Monthly energy production
- P50/P90 range
- Economic metrics (LCOE, ROI, NPV)
- Comparison with alternatives
- Environmental impact

========================================
SECTION 12: Cross-Topic Knowledge
========================================

PVsyst File Formats:
- .PAN: PV module parameters (single-diode model)
- .OND: Inverter parameters
- .PVW: Weather data (PVWatts format)
- .TMY: Typical Meteorological Year
- .csv: Generic data exchange

Data Flow in PVsyst:
1. Weather Data → Irradiation at module plane
2. Module Parameters → I/V characteristics
3. System Layout → Shading calculations
4. Electrical Design → Loss analysis
5. Simulation → Energy output
6. Economic Parameters → Financial metrics
7. Results → Reports & graphs

Key Performance Indicators:
- Performance Ratio (PR): 70-90% typical
- Specific Yield (kWh/kWp): Site dependent
- LCOE ($/kWh): Compare with grid price
- Capacity Factor: 10-30% for solar
- Degradation Rate: 0.5-0.75%/year

Database Sources:
- NREL/NSRDB: US and global
- PVGIS: European Union
- Meteonorm: Comprehensive global
- Solcast: Real-time/satellite-based
- Solar Anywhere: Asia-Pacific
- Solargis: Global

========================================
SECTION 13: PEA/Electricity Knowledge (Related)
========================================

[Cross-Reference to knowledge_processed]
For electricity tariff and PEA-related knowledge:
- See: D:\LocalAI\knowledge_processed\PEA_สรุป.md
- Electricity tariffs affect economic evaluation in PVsyst
- Feed-in tariff (FiT) defined by PEA/EGAT
- TOU (Time of Use) rates for grid-connected systems
- P50/P90 evaluations used for energy guarantee

========================================
SECTION 14: Version Comparison Quick Reference
========================================

PVsyst 7 vs 8 Key Differences:

| Feature | Version 7 | Version 8 |
|---------|-----------|-----------|
| Orientations | Single (limited) | Unlimited per system |
| 3D Scene | Basic | Advanced tools |
| Shading | Standard | Near + Far + Iso-shading |
| Sub-hourly | No | Yes (Meteonorm 9) |
| Bifacial | Basic | Advanced + Bifacial PR |
| Tracker | Single type | Flexible + Backtracking |
| UI | Standard | Dark mode, search, mkDocs |
| Batch | Manual | PVsystCLI + Batch mode |
| Economic | Basic | Full (CAPEX/OPEX/LCOE/NPV/ROI/IRR/PBP) |
| Databases | Standard | Updated + Import tools |

Version Timeline:
- Nov 2024: 8.0.0 (Major release)
- Feb 2025: 8.0.7
- Nov 2025: 8.0.19
- Apr 2026: 8.1.0 (Sub-hourly, new weather import)
- Aug 2026: 8.1.5 (Latest, Meteonorm 9.0.10)

========================================
SECTION 15: AI Model Training Notes
========================================

Topics the AI Model should understand:
1. PVsyst project workflow (project → design → simulation → results)
2. Orientation management (V8 key feature)
3. Loss analysis (before/after simulation)
4. Shading types (near vs far vs horizon)
5. Bifacial system modeling
6. P50/P90 probabilistic evaluation
7. Financial metrics (LCOE, ROI, NPV, IRR, PBP, CAPEX, OPEX)
8. .PAN file creation from datasheet
9. Tracker backtracking
10. GCR and row spacing optimization
11. Degradation and ageing analysis
12. Sub-hourly simulation importance
13. PVsyst file formats and data exchange
14. Solar irradiation sources and meteorological data
15. System types (grid-connected, off-grid, pumping, floating, DC-grid)

Knowledge Validation Questions:
- Why is sub-hourly meteorological data important?
- How does orientation management differ between V7 and V8?
- What is the difference between Module String and Module Layout shading?
- How is P50 different from P90?
- What does each component in LCOE represent?
- How does GCR affect system yield?
- Why is backtracking important for trackers?

========================================
END OF KNOWLEDGE BASE
Total Topics: 41/41
Generated from: PVsyst official docs + community posts
