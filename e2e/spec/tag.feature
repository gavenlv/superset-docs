# language: en
# BDD Spec — Tags (P4-F)

@tag
Feature: Tags
  As a curator
  I need to attach tags to dashboards, charts and saved queries for organization

  Scenario: List tags
    When the client calls "/api/v1/tag/"
    Then the response contains the tag list

  Scenario: Create a tag
    When the user creates a new tag
    Then the tag appears in the list
