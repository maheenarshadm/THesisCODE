"""Explicit, DISCLOSED human overrides for join ambiguities
`schema_utility.build_join_path` cannot safely resolve on its own --
same status as this project's own `[ASSUMED...]`-marked ground-truth
rows elsewhere (e.g. FLEX2's `variable_to_schema_mapping.csv`): a
researcher's domain-knowledge call, made explicit and inspectable here,
never silently guessed by the join-path BFS itself.

Each entry says WHICH of several syntactically-valid FK columns between
two tables is the semantically intended one, and WHY -- so anyone
reviewing this file sees exactly what was assumed and can dispute it.
`build_join_path` consults this BEFORE treating multiple FK columns
between the same two tables as an unresolvable ambiguity; an override
here is used, an ambiguity with no override here is still refused.

Format: {(case_study, from_table, to_table): {'column': ..., 'reason': ...}}
Table names must match the schema JSON's own canonical casing
(`schema_utility.canonical_table_name`).
"""

JOIN_DISAMBIGUATION = {
    ('OpenMRS', 'obs', 'concept'): {
        'column': 'concept_id',
        'reason': (
            "obs has two FK columns to concept: concept_id (the concept THIS "
            "OBSERVATION measures -- OpenMRS's standard EAV pattern) and "
            "value_coded (an unrelated CODED ANSWER value, only meaningful "
            "when the observation's own answer happens to be a concept). "
            "The decisions needing this join (Numeric Precision Validity, "
            "Numeric Absolute Range Validity, Numeric Interpretation "
            "Classification, Obs Value Required By Datatype) all read "
            "properties of the concept an observation is ABOUT (numeric "
            "range/precision/datatype), not properties of its answer value -- "
            "concept_id is the correct column. "
            "[ASSUMED by researcher domain knowledge of OpenMRS's EAV schema "
            "-- no ground-truth source citation available for this specific "
            "join; disclosed here rather than silently guessed.]"
        ),
    },
}


def get_override(case_study, from_table, to_table):
    return JOIN_DISAMBIGUATION.get((case_study, from_table, to_table))
