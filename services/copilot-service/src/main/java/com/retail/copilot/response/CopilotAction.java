package com.retail.copilot.response;

import java.util.Map;

public record CopilotAction(String type, Map<String, Object> data, String label) {}
