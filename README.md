# Recruitment Bias Detector & ATS Bias Simulation

Exposes how AI-powered hiring systems filter candidates based on bias signals not merit. Built with Streamlit and Claude on Amazon Bedrock.

## Demo

<!-- Replace with your screen recording GIFs -->

### Single Document Analysis
<!-- Paste a CV or JD → get a bias risk score with research-backed findings -->
<img width="800" height="440" alt="part1" src="https://github.com/user-attachments/assets/e341f5f6-6e13-49b0-b451-c1ff6dae0550" />

### CV Bias Simulation
<!-- Two CVs + one JD → simulates an LLM-based ATS and exposes whether the score gap is merit or bias -->
<img width="800" height="394" alt="part2" src="https://github.com/user-attachments/assets/d5d421cc-7661-44e9-9190-e83ab99bae59" />


### Job description Advise
<img width="800" height="394" alt="ScreenRecording2026-04-26at15 21 28-ezgif com-video-to-gif-converter" src="https://github.com/user-attachments/assets/25ce0ba1-befb-464d-8553-f8b6cc5911ef" />
## What it does

| Mode | Input | Output |
|---|---|---|
| **CV → Candidate view** | Your CV | What a biased screener would infer, with exact rewrites for what you can fix |
| **CV → Company view** | A candidate's CV | What your screening process risks penalising unfairly |
| **JD → Company view** | A job description | Who your JD accidentally excludes, with rewrites |
| **CV vs CV Simulation** | Two CVs + a JD | Head-to-head ATS simulation exposing whether the score gap is merit or bias |

## How the simulation works

The simulation scores both candidates on four metrics — not based on actual competence, but on what an LLM-based ATS would reward:

1. **Technical Match** — keyword and semantic matching against the JD
2. **Language & Framing** — agentic vs communal language, Western corporate English patterns
3. **Prestige Signal** — institution and employer name recognition bias
4. **Profile Coherence** — linear career path bias, gap penalties

It then ranks both candidates in a simulated pool of 500 and shows whether each reaches the recruiter — or gets filtered out before a human ever sees them.

![Simulation scoring breakdown](assets/demo-scoring.gif)

## Research backing

All findings cite peer-reviewed research:

- **Name bias**: Bertrand & Mullainathan (2004) — identical CVs with white-sounding names get 50% more callbacks
- **Gendered language**: Gaucher, Friesen & Kay (2011) — masculine-coded JDs reduce female applications by 5-7% per word
- **Prestige bias**: Rivera (2015) — screeners use university name as a class proxy, not a competence signal
- **Career gap penalty**: disproportionately affects women, caregivers, immigrants, and disabled candidates
- **EU AI Act**: recruitment AI is classified as high-risk (Article 6, Annex III) — bias audits are legally required

## Setup

### Prerequisites

- Python 3.11+
- AWS account with Bedrock access (Claude Sonnet model enabled)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/bias-simulation.git
cd bias-simulation

# Using uv (recommended)
uv sync

# Or using pip
pip install .
```

### Configure

```bash
cp .env.example .env
# Edit .env with your AWS credentials
```

Or configure AWS credentials via the CLI:

```bash
aws configure
```

### Run

```bash
streamlit run cv_analyzer/app.py
```

![App running locally](assets/demo-run.gif)

## Project structure

```
cv_analyzer/
├── app.py                 # Streamlit UI and Bedrock integration
├── bias_prompt.py         # Analysis prompts (CV candidate, CV company, JD company)
└── simulation_prompt.py   # ATS simulation prompt
```

## Try it yourself

Paste two CVs with identical qualifications but different names, universities, or career gaps. Watch the score gap open. Then click "Show me the mechanism" to see exactly what the system penalised.

## License

MIT
