package com.retail.copilot.response;

import java.util.List;

public record CopilotResponse(String answer, List<CopilotAction> actions) {}
