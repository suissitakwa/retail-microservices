package com.retail.copilot.controller;

import com.retail.copilot.request.CopilotRequest;
import com.retail.copilot.response.CopilotResponse;
import com.retail.copilot.service.CopilotService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/copilot")
@RequiredArgsConstructor
public class CopilotController {

    private final CopilotService copilotService;

    @PostMapping("/chat")
    public ResponseEntity<CopilotResponse> chat(@RequestBody CopilotRequest request,
                                                HttpServletRequest httpRequest) {
        String bearerToken = httpRequest.getHeader("Authorization");
        return ResponseEntity.ok(copilotService.chat(request, bearerToken));
    }
}
