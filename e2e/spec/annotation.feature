# language: en
# BDD Spec — Annotation Layers (P4-C)

@annotation
Feature: Chart annotation layers
  As a chart author
  I need to attach annotation layers to highlight events on the chart timeline

  Scenario: List annotation layers
    When the client calls "/api/v1/annotation_layer/"
    Then the response contains the annotation layer list

  Scenario: Create an annotation layer
    When the user creates an annotation layer
    Then the layer appears in the list

  Scenario: Delete an annotation layer
    Given an annotation layer exists
    When the user deletes that layer
    Then the layer is no longer in the list
