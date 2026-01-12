# IRAN CRISIS INTELLIGENCE COLLECTION REQUIREMENT
## Deep Research Query for Scenario Simulation

**Classification:** UNCLASSIFIED // FOR SIMULATION USE  
**Requirement ID:** IRAN-2026-001  
**Date:** January 10, 2026  
**Time Horizon:** 90 days (through April 10, 2026)

---

## SECTION 1: KEY INTELLIGENCE QUESTIONS

This research requirement is structured around five Key Intelligence Questions (KIQs). All data collection should serve to answer these questions. If data doesn't help answer a KIQ, deprioritize it.

### KIQ-1: REGIME STABILITY
**Will the Islamic Republic survive the current crisis in its present form over the next 90 days?**
- Sub-questions:
  - What is the state of elite cohesion? Are there observable fractures?
  - What is the loyalty/morale state of security forces, particularly IRGC ground units?
  - Does the regime retain sufficient coercive capacity to suppress protests?
  - Are there succession dynamics that could destabilize leadership?

### KIQ-2: PROTEST TRAJECTORY  
**Will protests escalate, sustain, or dissipate?**
- Sub-questions:
  - What is the current momentum (accelerating, stable, decelerating)?
  - Are protests developing organizational capacity, or remaining spontaneous?
  - Is there evidence of cross-cutting coalitions (bazaaris + students + ethnic minorities)?
  - What would cause protest collapse vs. breakthrough?

### KIQ-3: ETHNIC FRAGMENTATION
**Is there a meaningful probability of territorial fragmentation along ethnic lines?**
- Sub-questions:
  - Are ethnic militias (Kurdish, Baloch) coordinating with protests or pursuing separate agendas?
  - Is there evidence of cross-border support from Iraq, Pakistan, Azerbaijan, or Turkey?
  - Are there territorial control changes in peripheral regions?
  - What distinguishes current ethnic mobilization from 2022?

### KIQ-4: US INTERVENTION
**Under what conditions would the US intervene, and in what form?**
- Sub-questions:
  - What is the Trump administration's actual red line (vs. rhetorical posturing)?
  - What intervention options are operationally available on short notice?
  - What domestic and international constraints limit US action?
  - How does the June 2025 war precedent affect calculations?

### KIQ-5: REGIONAL CASCADE
**How would Iranian instability propagate regionally?**
- Sub-questions:
  - What would Israel do if regime appears to be collapsing?
  - How are Gulf states positioning?
  - What is Russia/China's stake and likely response?
  - What happens to Iranian proxies (Hezbollah remnants, Iraqi PMF, Houthis)?

---

## SECTION 2: COLLECTION PRIORITIES

### PRIORITY 1 - CRITICAL (Must have for simulation)
- Current protest metrics with time series (Day 1-14)
- Security force casualties and deployment patterns
- Defection indicators (observed signals AND absence of expected signals)
- Khamenei health/activity indicators
- US force posture and recent movements
- Economic data (rial, inflation, oil exports)

### PRIORITY 2 - IMPORTANT (Significantly improves simulation)
- Regime faction positioning and internal communications leaks
- Opposition organization development
- Ethnic armed group activity
- Regional actor statements and movements
- Historical base rates for calibration

### PRIORITY 3 - CONTEXTUAL (Nice to have)
- Detailed provincial breakdowns
- Infrastructure status
- Full comparative case studies
- Biographical details on secondary figures

---

## SECTION 3: SOURCING PROTOCOL

### Source Tiering (Two Dimensions)

**ACCESS QUALITY** - How do they know?
- **A - Direct**: Official statements, firsthand observation, leaked documents
- **B - Informed**: Well-placed sources, regional experts with networks
- **C - Derived**: Analysis of open source, inference from patterns
- **D - Speculative**: Opinion, prediction, single anonymous source

**BIAS ASSESSMENT** - What's their agenda?
- **1 - Neutral**: Wire services (Reuters, AP, AFP), academic institutions
- **2 - Positioned but professional**: Think tanks, quality regional media (Al-Monitor)
- **3 - Advocacy-adjacent**: Opposition-linked (Iran International), government-linked (IRNA)
- **4 - Advocacy**: MEK-affiliated, regime propaganda, partisan US outlets

**Cite as:** [A1], [B2], [C3], etc.

### Source Requirements by Claim Type
- **Factual claims (casualties, locations, dates)**: Require A1/A2/B1 or triangulation from 2+ B2/C1 sources
- **Structural claims (ethnic composition, IRGC holdings)**: B1/B2/C1 acceptable with date noted
- **Current assessments (morale, cohesion)**: Must flag as assessment, note source access level
- **Historical data**: Academic sources (C1) acceptable

### Mandatory Source Skepticism
- **Iranian government sources**: Assume undercount on protester casualties, overcount on security force casualties
- **Opposition sources (NCRI, MEK-affiliated)**: Assume overcount on protester numbers, overclaim on regime weakness
- **US government sources**: Note when assessments may serve policy objectives
- **Israeli sources**: Assess through lens of regime-change preference

---

## SECTION 4: OUTPUT SCHEMA

```json
{
  "metadata": {
    "requirement_id": "IRAN-2026-001",
    "generated_date": "2026-01-10T00:00:00Z",
    "data_cutoff": "2026-01-10T12:00:00Z",
    "crisis_day_count": 14,
    "analyst_notes": "string - overall assessment of collection quality"
  },

  "kiq_summaries": {
    "kiq_1_regime_stability": {
      "bottom_line": "string - 2-3 sentence assessment",
      "confidence": "HIGH|MODERATE|LOW",
      "key_evidence": ["list of most important data points"],
      "key_gaps": ["list of what we don't know that matters"]
    },
    "kiq_2_protest_trajectory": {
      "bottom_line": "string",
      "confidence": "HIGH|MODERATE|LOW", 
      "key_evidence": ["list"],
      "key_gaps": ["list"]
    },
    "kiq_3_ethnic_fragmentation": {
      "bottom_line": "string",
      "confidence": "HIGH|MODERATE|LOW",
      "key_evidence": ["list"],
      "key_gaps": ["list"]
    },
    "kiq_4_us_intervention": {
      "bottom_line": "string",
      "confidence": "HIGH|MODERATE|LOW",
      "key_evidence": ["list"],
      "key_gaps": ["list"]
    },
    "kiq_5_regional_cascade": {
      "bottom_line": "string",
      "confidence": "HIGH|MODERATE|LOW",
      "key_evidence": ["list"],
      "key_gaps": ["list"]
    }
  },

  "current_state": {
    "as_of": "2026-01-10T12:00:00Z",
    
    "protest_metrics": {
      "time_series": [
        {
          "date": "2025-12-28",
          "day_number": 1,
          "cities_affected": {"value": null, "source_grade": "B2"},
          "estimated_participants": {"low": null, "high": null, "source_grade": "C3"},
          "notable_events": ["list"]
        }
      ],
      "current_snapshot": {
        "provinces_affected": {"value": null, "of_total": 31, "source_grade": "A1"},
        "cities_affected": {"value": null, "source_grade": "B2"},
        "estimated_participants_current": {"low": null, "high": null, "methodology": "string"},
        "intensity_trend": "ESCALATING|PLATEAUED|DECLINING",
        "trend_evidence": "string - what supports this assessment"
      },
      "geographic_concentration": [
        {
          "region": "string",
          "provinces": ["list"],
          "intensity": "HIGH|MEDIUM|LOW",
          "ethnic_character": "string",
          "distinctive_features": "string"
        }
      ],
      "protest_character": {
        "primary_demands": ["list - economic vs political vs regime change"],
        "organizational_level": "SPONTANEOUS|LOOSELY_COORDINATED|ORGANIZED",
        "cross_class_coalition": "YES|PARTIAL|NO",
        "evidence": "string"
      }
    },

    "casualties": {
      "protesters": {
        "killed": {"low": null, "mid": null, "high": null, "source_grade": "B2"},
        "wounded": {"estimate": null, "source_grade": "C3"},
        "detained": {"estimate": null, "source_grade": "B2"}
      },
      "security_forces": {
        "killed": {
          "total": null,
          "irgc": null,
          "basij": null,
          "police": null,
          "source_grade": "B3"
        },
        "wounded": {"estimate": null, "source_grade": "B3"},
        "significance": "string - what does this indicate about protest intensity/armed resistance?"
      },
      "children": {"killed": null, "source_grade": "B2"}
    },

    "economic_conditions": {
      "rial_usd_rate": {
        "official": null,
        "market": null,
        "date": "2026-01-10",
        "30_day_change_percent": null,
        "all_time_low": true,
        "source_grade": "A1"
      },
      "inflation": {
        "official_annual_percent": null,
        "real_estimate_percent": null,
        "source_grade": "B1"
      },
      "oil_exports_bpd": {"value": null, "source_grade": "B1"},
      "regime_economic_response": {
        "measures_announced": ["list with dates"],
        "effectiveness_observed": "string"
      },
      "transmission_mechanism": "string - how economic pain translates to protest participation"
    },

    "information_environment": {
      "internet_status": {
        "current": "BLACKOUT|SEVERELY_DEGRADED|PARTIAL|FUNCTIONAL",
        "blackout_start": "date or null",
        "methodology": "string - how do we know?",
        "source_grade": "A1"
      },
      "regime_narrative": {
        "primary_frame": "string - how is regime characterizing protests?",
        "key_statements": [{"speaker": "string", "date": "date", "content": "string"}]
      },
      "external_information_access": {
        "starlink_penetration": "NONE|LIMITED|MODERATE|SIGNIFICANT|UNKNOWN",
        "vpn_usage": "string",
        "evidence": "string"
      }
    },

    "security_posture": {
      "force_deployment": {
        "level": "MAXIMUM|ELEVATED|STANDARD",
        "notable_movements": ["list"],
        "source_grade": "B2"
      },
      "rules_of_engagement_observed": {
        "live_fire": true,
        "mass_casualties_single_incident": {"occurred": true, "max_single_event": null},
        "escalation_trend": "INCREASING|STABLE|RESTRAINED"
      },
      "foreign_militia_deployment": {
        "confirmed": true,
        "groups_identified": [
          {
            "name": "string",
            "nationality": "string",
            "locations_reported": ["list"],
            "source_grade": "B3",
            "significance": "string"
          }
        ]
      }
    }
  },

  "regime_analysis": {
    "elite_cohesion": {
      "assessment": "UNIFIED|STRAINED|FRACTURING",
      "evidence_for_cohesion": ["list"],
      "evidence_for_strain": ["list"],
      "key_relationships_to_watch": ["list"]
    },
    
    "factions": [
      {
        "name": "string (e.g., 'IRGC Hardliners', 'Reformist Government')",
        "key_figures": [{"name": "string", "title": "string"}],
        "institutional_base": "string",
        "current_stance_on_crisis": "string",
        "interests_at_stake": ["list"],
        "recent_statements_actions": [{"date": "date", "action": "string"}]
      }
    ],

    "khamenei": {
      "age": 86,
      "health_indicators": {
        "public_appearances_last_30_days": null,
        "appearance_quality": "NORMAL|DIMINISHED|CONCERNING",
        "health_rumors": "string",
        "source_grade": "C3"
      },
      "recent_statements": [{"date": "date", "content": "string", "tone": "string"}],
      "succession_status": {
        "designated_successor": "string or null",
        "assembly_of_experts_activity": "string",
        "competing_candidates": ["list"]
      }
    },

    "security_force_loyalty": {
      "irgc": {
        "assessment": "LOYAL|MIXED|QUESTIONABLE",
        "defection_signals_observed": ["list or 'none'"],
        "defection_signals_absent": ["list - what we'd expect to see if defection imminent"],
        "morale_indicators": "string",
        "key_units_to_watch": ["list with rationale"]
      },
      "basij": {
        "assessment": "LOYAL|MIXED|QUESTIONABLE",
        "evidence": "string"
      },
      "regular_military": {
        "assessment": "LOYAL|NEUTRAL|QUESTIONABLE",
        "role_in_current_crisis": "string",
        "evidence": "string"
      }
    },

    "regime_options": {
      "option_space": [
        {
          "option": "string (e.g., 'Maximum Crackdown', 'Managed Concessions')",
          "description": "string",
          "historical_precedent": "string",
          "indicators_if_chosen": ["list - what would we see?"]
        }
      ],
      "perceived_constraints": "string - what do regime leaders believe limits their options?"
    },

    "counter_mobilization_capacity": {
      "pro_regime_demonstrations": {
        "occurred": true,
        "estimated_participation": null,
        "locations": ["list"],
        "organic_vs_organized": "string"
      },
      "basij_mobilization_reserve": "string",
      "clerical_support": "STRONG|MIXED|WEAK"
    }
  },

  "opposition_analysis": {
    "protest_movement": {
      "leadership": "DECENTRALIZED|EMERGENT_LEADERS|ORGANIZED",
      "named_leaders": ["list or 'none identified'"],
      "coordination_mechanisms": "string",
      "stated_demands": ["list - distinguish economic vs political vs regime change"],
      "strategic_coherence": "string"
    },

    "diaspora_organizations": [
      {
        "name": "string",
        "leadership": "string",
        "claimed_role": "string",
        "credibility_assessment": "string",
        "actual_influence_inside_iran": "SIGNIFICANT|LIMITED|NEGLIGIBLE|UNKNOWN"
      }
    ],

    "ethnic_armed_groups": [
      {
        "name": "string",
        "ethnicity": "KURDISH|BALOCH|ARAB|OTHER",
        "estimated_strength": "string",
        "geographic_base": "string",
        "recent_actions": [{"date": "date", "action": "string"}],
        "foreign_backing": "string or null",
        "coordination_with_protests": "YES|LIMITED|NO|UNKNOWN",
        "separatist_vs_federalist": "string"
      }
    ],

    "bazaari_role": {
      "current_participation": "ACTIVE|PARTIAL|WITHDRAWN",
      "historical_significance": "string",
      "economic_interests": "string",
      "political_alignment_shift": "string"
    }
  },

  "external_actors": {
    "united_states": {
      "stated_position": {
        "quotes": [{"speaker": "string", "date": "date", "content": "string"}],
        "policy_documents": ["list or null"]
      },
      "force_posture": {
        "troops_in_region": {"estimate": null, "source_grade": "B1"},
        "naval_assets": "string",
        "air_assets": "string",
        "recent_movements": ["list"],
        "bases_relevant": [{"name": "string", "country": "string", "capabilities": "string"}]
      },
      "intervention_options_available": [
        {
          "option": "string",
          "category": "INFORMATION|ECONOMIC|CYBER|COVERT|KINETIC",
          "description": "string",
          "precedent": "string",
          "readiness_level": "IMMEDIATE|DAYS|WEEKS",
          "escalation_category": "LOW|MEDIUM|HIGH|EXTREME"
        }
      ],
      "domestic_constraints": {
        "congressional": "string",
        "public_opinion": "string",
        "pentagon_assessment": "string",
        "key_voices": [{"name": "string", "position": "string", "stance": "string"}]
      },
      "june_2025_precedent": {
        "what_happened": "string",
        "how_it_affects_current_calculations": "string"
      }
    },

    "israel": {
      "stated_position": "string",
      "recent_actions": ["list"],
      "capabilities_relevant": "string",
      "interests": ["list"],
      "constraints": ["list"]
    },

    "russia": {
      "stated_position": "string",
      "interests": ["list"],
      "support_to_iran": "string",
      "constraints": ["list - Ukraine war impact?"]
    },

    "china": {
      "stated_position": "string",
      "economic_ties": "string",
      "interests": ["list"],
      "likely_stance_if_regime_falls": "string"
    },

    "gulf_states": {
      "saudi_arabia": {"position": "string", "interests": "string"},
      "uae": {"position": "string", "interests": "string"},
      "qatar": {"position": "string", "interests": "string"}
    },

    "regional_neighbors": {
      "iraq": {"position": "string", "pmu_activity": "string"},
      "turkey": {"position": "string", "kurdish_dimension": "string"},
      "pakistan": {"position": "string", "baloch_dimension": "string"},
      "azerbaijan": {"position": "string", "azeri_dimension": "string"}
    }
  },

  "structural_data": {
    "ethnic_composition": [
      {
        "group": "string",
        "population_percent": null,
        "population_millions": null,
        "primary_provinces": ["list"],
        "historical_grievance_level": "HIGH|MEDIUM|LOW",
        "armed_groups_present": ["list or null"],
        "cross_border_kin_state": "string or null",
        "current_mobilization": "HIGH|MEDIUM|LOW|MINIMAL"
      }
    ],

    "irgc_structure": {
      "estimated_personnel": null,
      "economic_holdings": {
        "estimated_value_usd_billions": {"low": null, "high": null},
        "key_sectors": ["list"],
        "source_grade": "C1"
      },
      "post_june_2025_status": {
        "leadership_losses": ["list of commanders killed in 12-day war"],
        "capability_degradation": "string",
        "reconstitution_status": "string"
      }
    },

    "military_capabilities": {
      "nuclear_status": {
        "enrichment_current": "NONE|LOW|MEDIUM|HIGH|UNKNOWN",
        "post_june_2025_assessment": "string"
      },
      "missile_inventory": "DEPLETED|REDUCED|REBUILDING|MAINTAINED",
      "air_defense": "DEGRADED|FUNCTIONAL",
      "asymmetric_capabilities": "string"
    },

    "proxy_network_status": {
      "hezbollah": "DESTROYED|SEVERELY_DEGRADED|DEGRADED|FUNCTIONAL",
      "iraqi_pmu": "string",
      "houthis": "string",
      "overall_assessment": "string"
    }
  },

  "historical_base_rates": {
    "iranian_protests": [
      {
        "event": "string",
        "year": null,
        "duration_days": null,
        "trigger": "string",
        "peak_geographic_scope": "string",
        "peak_participation_estimate": "string",
        "regime_response": "string",
        "outcome": "SUPPRESSED|PARTIAL_CONCESSIONS|REGIME_CHANGE",
        "casualties": null,
        "defections_occurred": true,
        "key_factors_in_outcome": ["list"]
      }
    ],

    "regime_survival_record": {
      "crises_survived": ["list with years"],
      "survival_mechanisms_used": ["list"],
      "closest_calls": ["list with analysis"]
    },

    "comparative_cases": [
      {
        "country": "string",
        "year": null,
        "event": "string",
        "outcome": "string",
        "duration": "string",
        "key_parallels_to_iran": ["list"],
        "key_differences_from_iran": ["list"],
        "lessons": ["list"]
      }
    ],

    "defection_patterns": {
      "historical_cases": [
        {
          "country": "string",
          "year": null,
          "what_preceded_defection": ["list"],
          "what_triggered_defection": "string",
          "time_from_first_signal_to_defection": "string"
        }
      ],
      "iran_specific": "string - history of security force defections in Iran"
    }
  },

  "scenario_observables": {
    "regime_survival_indicators": {
      "positive_for_survival": [
        {
          "indicator": "string",
          "currently_observed": "YES|NO|PARTIAL",
          "evidence": "string"
        }
      ],
      "negative_for_survival": [
        {
          "indicator": "string", 
          "currently_observed": "YES|NO|PARTIAL",
          "evidence": "string"
        }
      ]
    },

    "imminent_crackdown_indicators": [
      {
        "indicator": "string",
        "currently_observed": "YES|NO",
        "evidence": "string"
      }
    ],

    "defection_warning_indicators": [
      {
        "indicator": "string",
        "currently_observed": "YES|NO",
        "evidence": "string"
      }
    ],

    "fragmentation_warning_indicators": [
      {
        "indicator": "string",
        "currently_observed": "YES|NO",
        "evidence": "string"
      }
    ],

    "us_intervention_warning_indicators": [
      {
        "indicator": "string",
        "currently_observed": "YES|NO",
        "evidence": "string"
      }
    ]
  },

  "geographic_data": {
    "provinces": [
      {
        "name": "string",
        "population_millions": null,
        "primary_ethnicity": "string",
        "current_protest_status": "HIGH|MEDIUM|LOW|NONE",
        "key_cities_affected": ["list"],
        "strategic_features": "string",
        "borders": ["list of countries or null"]
      }
    ],

    "critical_infrastructure": [
      {
        "name": "string",
        "type": "OIL|GAS|MILITARY|NUCLEAR|GOVERNMENT|PORT",
        "province": "string",
        "coordinates": {"lat": null, "lon": null},
        "strategic_value": "CRITICAL|HIGH|MEDIUM",
        "current_status": "string"
      }
    ]
  },

  "sources": [
    {
      "id": "string",
      "organization": "string",
      "title": "string",
      "date": "YYYY-MM-DD",
      "url": "string",
      "access_grade": "A|B|C|D",
      "bias_grade": "1|2|3|4",
      "notes": "string"
    }
  ],

  "collection_assessment": {
    "overall_confidence": "HIGH|MODERATE|LOW",
    "strongest_sections": ["list"],
    "weakest_sections": ["list"],
    "critical_gaps": [
      {
        "gap": "string",
        "impact_on_analysis": "string",
        "collection_recommendation": "string"
      }
    ],
    "source_limitations": ["list"],
    "potential_biases_in_collection": ["list"],
    "red_team_challenges": [
      {
        "assumption": "string - what are we assuming that could be wrong?",
        "alternative_interpretation": "string",
        "evidence_that_would_falsify": "string"
      }
    ]
  }
}
```

---

## SECTION 5: RESEARCH EXECUTION GUIDANCE

### Phase 1: Current Crisis State (Priority 1)
Start with wire services from last 24 hours. Establish:
- Today's protest locations and intensity
- Latest casualty figures (triangulate HRANA, opposition sources, regime sources)
- Security force response level
- Internet status

### Phase 2: Trajectory Analysis (Priority 1)
Build the time series:
- Day-by-day protest spread from Dec 28
- Identify inflection points
- Characterize momentum

### Phase 3: Actor Deep Dives (Priority 1-2)
For each actor category:
- Recent statements with dates
- Observed actions
- Inferred interests and constraints

### Phase 4: Structural Context (Priority 2)
- Ethnic composition and current mobilization by group
- IRGC status post-June 2025
- Economic transmission mechanisms

### Phase 5: Historical Calibration (Priority 2)
- 1979, 2009, 2017-18, 2019, 2022 protest data
- Comparative cases (Syria, Libya, Venezuela)
- Defection patterns from analogous cases

### Phase 6: Scenario Observables (Priority 1)
For each possible outcome, identify:
- What we would see beforehand
- What we currently observe
- What's absent

---

## SECTION 6: OUTPUT REQUIREMENTS

1. **Valid JSON only** - Parse before submitting
2. **No fabrication** - Use null with explanation for unknowns
3. **Source grades on all claims** - [A1] through [D4]
4. **Uncertainty explicit** - Ranges, not point estimates; confidence levels stated
5. **KIQ summaries first** - These are the product; everything else is supporting evidence
6. **Red team section substantive** - At least 3 genuine challenges to key assumptions
7. **Gaps acknowledged** - What we don't know matters as much as what we do

---

## SECTION 7: VALIDATION CHECKLIST

Before submission:
- [ ] JSON parses without error
- [ ] All KIQ summaries completed with bottom line assessments
- [ ] Time series has entries for all 14 days (with nulls where unknown)
- [ ] Every factual claim has source grade
- [ ] Scenario observables section completed for all 5 outcome types
- [ ] Red team section has 3+ substantive challenges
- [ ] No placeholder text remains
- [ ] Sources section complete with access/bias grades
- [ ] Geographic data sufficient for mapping (all 31 provinces)
