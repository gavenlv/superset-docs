# language: en
# BDD Spec — CSS Templates (P4-D)

@css
Feature: CSS templates (custom themes)
  As an administrator
  I need to apply custom CSS rules to brand the UI

  Scenario: List CSS templates
    When the client calls "/api/v1/css_template/"
    Then the response contains the CSS template list

  Scenario: Create a CSS template
    When the user creates a CSS template
    Then the template appears in the list
