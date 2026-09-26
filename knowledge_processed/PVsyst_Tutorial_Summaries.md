# PVsyst Tutorial Summaries
# Extracted from Official PVsyst PDF Tutorials
# Generated: 2026-09-19

========================================
TUTORIAL 1: Grid Connected Systems (v8)
Source: PVsyst official tutorial (4.96 MB, ~300+ pages)
File: pvsyst_tutorial_grid.txt

Key Topics Covered:
1. Project Definition and Workflow
   - Project setup (location, weather, type)
   - Variant management
   - Hierarchy: Projects → Variants → System definitions

2. 3D Scene and Shading
   - Near shading: 3D scene modeling
   - Horizon: Sun position profile
   - ISO-shadings diagram
   - Module Layout vs Module String shading calculation

3. System Definition
   - Module selection (PAN files)
   - Inverter selection (OND files)
   - String configuration
   - Multi-MPPT and power sharing

4. Detailed Losses
   - Thermal parameters (Uc coefficient)
   - Ohmic losses (DC and AC)
   - Module quality loss
   - Module mismatch loss
   - IAM factor
   - Soiling loss
   - LID (Light Induced Degradation)
   - Spectral losses

5. Results Analysis
   - Loss diagram
   - Performance Ratio (PR)
   - Normalized performance index
   - Monthly/Daily yield indicators
   - P50/P90 evaluation

6. Economic Evaluation
   - Installation and operating costs
   - Financial parameters
   - LCOE, ROI, NPV, IRR, PBP

========================================
TUTORIAL 2: Components Database (PAN/OND Files)
Source: PVsyst official tutorial (1.19 MB, 13 pages)
File: pvsyst_tutorial_components.txt

Module Definition from Datasheet (Step by Step):
1. Basic Data tab:
   - Model name
   - Manufacturer (exact name)
   - Data source (and date)
   - File name: "Manufacturer_Model.PAN" (must be unique)

2. Manufacturer Specifications:
   From Datasheet page 2:
   - Nom power (nameplate): e.g., 325 Wp
   - Tolerance: % of Pnom
   - Technology: Poly/Mono/Thin-film
   - STC values: Impp, Vmpp, Isc, Voc
     * NB: Vmpp × Impp must match Pnom within 0.2%
   - NOCT: NOT used in PVsyst!
   - Reverse current feed: NOT used in PVsyst!

3. Sizes and Technology tab:
   - Module size (mandatory - determines efficiency)
   - Cells number (mandatory - per cell model)
   - Cell size and area
   - Maximum IEC/UL voltage (1500V for new modules)
   - Number of bypass diodes (used for Module Layout losses)

4. Model Parameters tab:
   - Rshunt and Rserie (leave defaults, check boxes)
   - Rshunt exponential
   - Temperature coefficient (Pmpp defined)
   - μVoc (result of model, cannot match datasheet)

5. Graphs tab:
   - I/V curve visualization for any irradiance/temperature

6. Additional Data tab:
   - Secondary parameters
   - IAM profile (optional, special AR coating)
   - Low-light data (if measured)
   - Measured I/V curve (determine model from measurement)

7. Commercial tab:
   - Manufacturer coordinates
   - Availability dates
   - Component prices

Inverter Definition (OND files):
1. Basic Data (same structure as module):
   - Filename: "Manufacturer_Model.OND"

2. Input Side:
   - Min/Max MPP voltage (clip voltage range)
   - Min voltage for Pnom (current limitation)
   - Absolute Maximum PV voltage (safety limit)
   - Power threshold (>0.5% of Pnom)

3. Output Side (Grid Connection):
   - Frequency (60Hz US, 50Hz Europe)
   - Grid voltage (400V Europe)
   - Nominal AC Power (apparent power [kVA] if phase shift allowed)
   - Nominal/Max AC current (not used in PVsyst)

4. Efficiency:
   - Max efficiency
   - CEC efficiency
   - Efficiency at 3 voltages

5. Additional parameters:
   - Multi-MPPT capability
   - Number of MPPT inputs (used for system definition)
   - Auxiliary consumptions (for detailed losses)

6. Output parameters:
   - Power factor (Phase shift capability)
   - Tan(phi) min/max
   - PNom definition (Active [kW] vs Apparent [kVA])
   - Max AC power f(Temperature)
   - Allows overpower (with definition)

Important Rules:
- "Show optimization" button: real-time parameter effect visualization
- "Copy to table" button: export to Excel
- Easier to modify existing component than create from scratch
- Transformerless inverter + amorphous module = WARNING!

========================================
TUTORIAL 3: PVsyst 8.1 Grid Connected (Comprehensive)
Source: PVsyst official tutorial v8.1 (10.69 MB, ~300+ pages)
File: pvsyst_tutorial_v81.txt

New in v8.1:
1. Sub-hourly Simulation:
   - Weather data at sub-hourly intervals
   - Clipping correction
   - More accurate results for:
     * Self-consumption analysis
     * Battery optimization
     * Time-of-use tariff analysis

2. Weather Data Import Assistant:
   - Step-by-step weather data import
   - Source selection guidance
   - Automatic validation

3. Meteonorm 9:
   - Updated database
   - New climate data periods (1996-2015, 2000-2019)
   - Improved accuracy

4. Bifacial 3D Modeling:
   - Detailed rear irradiance calculation
   - 3D bifacial model
   - Bifacial PR calculation

5. Expanded AC Circuit:
   - More detailed grid connection modeling
   - Transformer modeling
   - Power flow analysis

6. Batch Mode:
   - Automated simulation runs
   - Parametric studies
   - Optimization workflows

========================================
PVPMC 2025: PVsyst Updates
Source: PVPMC 2025, Michele Oliosi (PVsyst SA)
File: PVPMC_2025_PVsyst_Updates.txt

Timeline:
- Nov 2024: PVsyst 8.0.0 (Major release)
- May 2025: PVsyst 8.0.12 (Batch mode in PVsystCLI)
- End 2025: PVsyst 8.1 (Full sub-hourly, 3D bifacial, batch)
- PVsystCLI: Separate product for automation

PVsyst 8 Feature Summary:
System Design:
- Any orientation number/type within one system
- More flexible bifacial modeling
- More flexible tracker modeling

UI Improvements:
- New 3D scene tools (quality of life)

Modeling:
- Optional sub-hourly clipping correction
- General model improvements

PVsystCLI + Batch (8.0.12):
- Automated parametric simulation
- Use case: System optimization with custom algorithm
- Workflow:
  1. System set-up (site, weather, variants, project)
  2. Define batch parameters (orientation, system, variants)
  3. Run PVsystCLI batch (synthetic/timeseries data)
  4. Load results
  5. Optimization algorithm → Optimized Design

Orientation Analysis Tool (Stage 1):
- Problem: On uneven terrain, individual table orientation ≠ modeled average orientation → modeling error
- Current: Analysis of impact on POA irradiance
- Field orientation distribution analysis
- Base slope spread across all tables
- Weighted transposition error calculation
- Transposition error vs base slope analysis
- Future: Analysis via electrical mismatch

Updated Partition Shading Guidelines:
- Two shading calculation methods:
  1. Detailed IV curve evaluation (accurate, slow)
  2. Partition approximation (faster, regular rows)
- Partition: divides PV surfaces → shading factor
- Key parameter: Number of partitions
- Shading depends on:
  - DC array components and layout
  - Weather (diffuse fraction)
- Partition configurations:
  - 1 row landscape (1L): 2 partitions
  - 1 row half-cut portrait (1T): 2 partitions
  - 2 rows landscape in parallel (2L): 2 partitions
  - More complex: more partitions needed
- "More cloudy" vs "Sunnier" configuration choices

Future PVsyst 8.1 Features:
🌦 New interface for weather data import
🌦 Major update of Meteonorm
⏱ Sub-hourly import and simulation
⛱ Bifacial 3D modeling
🔌 Expanded AC circuit
📚 Novelties for batch mode

Outlook:
- Full sub-hourly simulation
- 3D bifacial model
- New batch mode
- Solar glare analysis
- Mismatch from orientations
- Measured data analysis
- New AC circuit
- New weather data import

========================================
Tutorial File Locations
========================================

D:\LocalAI\knowledge_processed\PVsyst_Tutorials\
├── pvsyst_tutorial_grid.txt (123 KB) - Grid Connected tutorial summary
├── pvsyst_tutorial_components.txt (14 KB) - Components/PAN tutorial
├── pvsyst_tutorial_v81.txt (239 KB) - v8.1 comprehensive tutorial
└── PVPMC_2025_PVsyst_Updates.txt (4 KB) - PVPMC presentation summary

Original PDFs also available:
D:\AMR_Fetcher\PVsyst_Tutorials\
├── pvsyst-tutorial-v8-grid-connected-en.pdf (4.96 MB)
├── pvsyst-tutorial-v8-components-database-en.pdf (1.19 MB)
└── pvsyst-tutorial-v8.1-grid-connected-en.pdf (10.69 MB)

========================================
END OF TUTORIAL SUMMARIES
