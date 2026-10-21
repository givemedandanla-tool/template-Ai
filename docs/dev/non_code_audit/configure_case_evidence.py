"""Human-selected assertion intents; names are resolved to actual source bodies."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/dev/non_code_audit/execution-001'

ROWS=[
 ('A01','Later rules are scoped;withdrawn customer commands are refused,not all professional editing.', ['test_design_synthesis.test_cycles_and_customer_fine_parameter_commands_are_rejected']),
 ('A02','Multiple matching roles need declared permission/default;one physical container cannot be allocated twice.', ['test_design_assignment.test_cross_type_substitution_requires_policy_even_with_observed_same_container','test_design_assignment.test_one_equivalent_container_cannot_be_double_allocated_or_borrowed_across_people']),
 ('A03','Finite independent matchings provideSAT/UNSAT witnesses;explicit relative cycles must be rejected.', ['test_noncode_invariants.test_small_exhaustive_matching_oracle_finds_both_sat_and_unsat','test_noncode_invariants.test_contradictory_relative_cycle_is_rejected_instead_of_silently_dropped']),
 ('A04','Shared family learning is distinct from import count/template creation and real qualification.', ['test_noncode_invariants.test_shared_style_is_not_one_family_per_work_and_aliases_do_not_create_support','test_design_learning.test_freeze_uses_existing_store_and_pins_roles_without_creating_templates']),
 ('B01','Explicit format candidates preserve original string values and customer leading zeros.', ['test_noncode_invariants.test_explicit_semantic_candidates_do_not_mutate_original_strings','test_noncode_invariants.test_engineering_input_budget_rejects_without_silent_truncation','test_customer_candidates.test_review_and_commit_keep_leading_zeros_exact_versions_and_source_scope']),
 ('B02','Equal strings are not shared identity;explicit shared users retain one source owner and stable field IDs.', ['test_noncode_invariants.test_same_text_and_shared_use_keep_distinct_identity_and_owner','test_noncode_invariants.test_clearing_one_value_keeps_other_value_stable_id_and_position']),
 ('B03','Explicit size units do not infer identity;unframed candidate crops need review;multiwork state reopens exactly.', ['test_source_region_hypotheses.test_explicit_units_are_required_and_normalized_without_identity_inference','test_source_region_hypotheses.test_separated_unframed_works_have_review_only_size_conditioned_crops','test_artwork_recovery.test_two_works_reopen_active_selection_and_marks']),
 ('B04','Unknown/default/nonuniform typography cannot become source truth.', ['test_design_observation.test_anisotropy_shear_unknown_and_template_defaults_do_not_become_source_pt','test_design_observation.test_unknown_defaults_untraceable_and_nonfinite_metrics_rejected']),
 ('C01','Correlated sources cannot cross dataset roles;sealedHOLDOUT never fits.', ['test_design_learning.test_cross_file_correlations_cannot_span_dataset_roles','test_noncode_invariants.test_holdout_cannot_be_used_to_fit_even_if_appearance_matches']),
 ('C02','Independent shared structure is learned;raw customer text/default fonts do not become family features;equivalent semantic substitutions can share geometry.', ['test_noncode_invariants.test_family_features_ignore_customer_text_and_unverified_defaults','test_noncode_invariants.test_shared_style_is_not_one_family_per_work_and_aliases_do_not_create_support','test_design_family.test_batch_reestimation_is_deterministic_and_preserves_rare_observations','test_design_family.test_equivalent_semantic_substitution_does_not_itself_split_geometry_families']),
 ('C03','Known negatives cannot enlarge/support the suitable region;conditional maxima stay in their own context.', ['test_noncode_capacity_semantics.test_known_unqualified_outlier_cannot_expand_suitable_region','test_noncode_capacity_semantics.test_known_layout_failure_inside_otherwise_supported_region_abstains','test_noncode_capacity_semantics.test_conditional_advice_does_not_borrow_other_context_field_count','test_design_joint.test_extrapolation_and_unobserved_joint_input_holes_abstain']),
 ('C04','Synthetic evaluation is not a real-corpus certificate;forged/generated references cannot authorize production.', ['test_design_feedback_qualification.test_synthetic_evaluation_cannot_obtain_real_corpus_certificate','test_design_feedback_qualification.test_forged_qualification_state_or_generated_reference_cannot_enable_formal_output','test_design_rule_extensions.test_explicit_production_quality_policy_rejects_synthetic_or_incomplete_evidence']),
 ('D01','A→B and B→C in different contexts do not imply A→C;cross-owner borrowing is rejected.', ['test_noncode_invariants.test_cross_type_permissions_do_not_create_transitive_container_access','test_noncode_invariants.test_semantic_default_and_owner_survive_nonsemantic_enumeration_order']),
 ('D02','An explicit legal swap stays in the family;unsupported overcapacity is not silently truncated.', ['test_design_synthesis.test_same_input_repeat_and_explicit_swap_keep_same_family_and_stable_geometry','test_design_synthesis.test_oversized_input_is_retained_and_cannot_be_silently_truncated']),
 ('D03','Unmoved pair topology is protected;actual pointer edits affect intent,not data;core controls typography.', ['test_desktop_workspace.test_embedded_pointer_drag_keeps_same_core_intent_and_data','test_design_synthesis.test_source_observed_expanded_width_is_core_controlled_and_actually_measured','test_design_synthesis.test_distributed_style_uses_conditional_source_bounds_and_actual_fixed_pt_measurement']),
 ('D04','Explicit defaults are invariant to nonsemantic role enumeration;accepted artifacts reuseexact bytes after model change.', ['test_noncode_invariants.test_profile_enumeration_order_is_not_a_new_customer_preference','test_noncode_invariants.test_semantic_default_and_owner_survive_nonsemantic_enumeration_order','test_design_session.test_accepted_artifact_reuses_exact_bytes_after_new_model_activation']),
 ('E01','An unconfirmed/changed input cannot reuse an approval or publish output.', ['test_noncode_invariants.test_unconfirmed_and_changed_data_cannot_reuse_confirmation','test_final_digital_preflight.test_candidate_mutation_during_encoding_cannot_publish_stale_approval']),
 ('E02','Correcting content and undoing layout preserve new phone/owner;real modal input invalidates and regenerates preview.', ['test_design_session.test_correct_data_then_undo_layout_preserves_new_phone_and_owner','test_desktop_workspace.test_real_main_input_edit_invalidates_old_canvas_then_regenerates_latest_data']),
 ('E03','Cancel/resume retains completed items;late solves cannot install obsolete input.', ['test_training_pipeline.test_cooperative_cancel_after_actual_item_then_reopen_resume_no_success_rerun','test_design_session.test_late_solve_cannot_install_old_data_over_new_input']),
 ('E04','New current models do not rewrite accepted artifacts;external revisions invalidate the old displayed confirmation.', ['test_design_session.test_accepted_artifact_reuses_exact_bytes_after_new_model_activation','test_desktop_workspace.test_external_session_revision_clears_embedded_old_result_and_confirmation']),
 ('F01','Declared units and actual encoded dimensions are independently checked.', ['test_source_region_hypotheses.test_explicit_units_are_required_and_normalized_without_identity_inference','test_final_digital_preflight.test_valid_png_wrong_pixels_cannot_publish_on_dimensions_alone']),
 ('F02','Actual shaping is bounded;missing typography is unknown;oversized data is retained,not cut.', ['test_noncode_invariants.test_unfittable_string_is_kept_and_cannot_be_promoted_to_a_complete_draft','test_design_synthesis.test_missing_source_typography_is_unknown_instead_of_default_font','test_design_rule_extensions.test_single_cluster_and_combining_mark_are_not_split']),
 ('F03','Every new dynamic value is present with correct owner;whole Logo may carry company name only by its supported contract.', ['test_noncode_invariants.test_authored_complete_data_and_nonoverlap_are_independent_output_invariants','test_design_logo_synthesis.test_complete_logo_carries_company_name_without_silent_omission']),
 ('F04','A preview/computation success is not formal encoded output or physical print proof.', ['test_design_session.test_actual_source_bound_model_input_solve_confirm_and_preview_output','test_digital_preflight.test_real_complete_candidate_still_needs_actual_encoded_format_evidence','test_final_digital_preflight.test_corrupt_pdf_after_page_box_writer_cannot_publish']),
 ('G01','A real small desktop retains primary work/canvas and task guidance;independent novice learning is not measured by developer tests.', ['test_desktop_workspace.test_small_window_keeps_primary_and_canvas_visible_without_scrolling','test_desktop_workspace.test_real_guidance_navigation_opens_four_task_pages']),
 ('G02','Plain summaries and detailed reports omit authored sensitive canaries while retaining real measurements.', ['test_noncode_invariants.test_safe_local_production_report_contains_measurements_not_customer_text','test_offline_support.test_report_roundtrip_has_beginner_summary_and_no_private_content','test_diagnostic_reports.test_all_payloads_omit_synthetic_personal_ids_paths_notes_and_unknown_errors']),
 ('G03','Prepared local runtime refuses remote resources and network;observe real desktop operations underOS syscall tracing.', ['test_offline_support.test_remote_svg_references_are_blocked_but_displayed_urls_and_embedded_images_remain','test_offline_support.test_python_network_guard_blocks_ipv4_ipv6_dns_and_unc_but_allows_unix']),
 ('G04','Batch failures remain counted;retry/restore does not overwrite newer values or silently duplicate work.', ['test_batch_correction_source.test_eight_applied_two_failed_one_manual_counts_are_exact_and_not_global_pass','test_batch_correction_source.test_relative_move_retry_reads_existing_operation_instead_of_moving_twice','test_relational_backup.test_authenticated_unknown_schema_is_blocked_and_incomplete_restore_cannot_open_as_library']),
 ('H01','Each current clause maps to a normative expectation and assertion;current source and formal provenance are distinct.', []),
 ('H02','Only actual fresh remote tree/blob proof authorizes remote status;local restore verification does not impersonate GitHub.', []),
 ('H03','Wrong owners,cycles,unqualified support,stale confirmations and tampered evidence must be rejected in isolated controls.', ['test_noncode_invariants.test_contradictory_relative_cycle_is_rejected_instead_of_silently_dropped','test_noncode_capacity_semantics.test_known_unqualified_outlier_cannot_expand_suitable_region','test_noncode_invariants.test_unconfirmed_and_changed_data_cannot_reuse_confirmation']),
 ('H04','Resume uses explicit saved version,counts,scope and next step;no silent promotion or dependence on chat history.', [])
]


def main():
    cases=[];allrefs={}
    for case,note,refs in ROWS:
        items=[]
        for ref in refs:
            mod,method=ref.split('.',1);path=ROOT/'tests'/f'{mod}.py';source=path.read_text();matches=[]
            for cls in ast.parse(source).body:
                if not isinstance(cls,ast.ClassDef):continue
                for fn in cls.body:
                    if isinstance(fn,ast.FunctionDef) and fn.name==method:matches.append((cls,fn))
            assert len(matches)==1,(ref,len(matches))
            cls,fn=matches[0];identity=f'{mod}.{cls.name}.{fn.name}'
            statements=[ast.unparse(n) for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert')]
            assert statements,(ref,'no actual assertion anchor')
            body='\n'.join(source.splitlines()[fn.lineno-1:fn.end_lineno])
            entry=dict(test_id=identity,path=path.relative_to(ROOT).as_posix(),line=fn.lineno,
                       function_sha256=hashlib.sha256(body.encode()).hexdigest(),assertions=statements,
                       limits='Assertion intent reviewed in approved scoped context;not proof of all branches or real-corpus quality.')
            allrefs[identity]=entry;items.append(identity)
        cases.append(dict(id='NCA-'+case,independent_expected_intent=note,test_refs=items,
                          review_basis='Human-authored normative intent plus actual assertion source anchors,not test name matching alone.'))
    assert len(cases)==32
    (OUT/'case-evidence-plan.json').write_text(json.dumps(dict(cases=cases,source_assertions=allrefs),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),selected_actual_tests=len(allrefs),all_selected_have_assertions=True)))


if __name__=='__main__':main()
