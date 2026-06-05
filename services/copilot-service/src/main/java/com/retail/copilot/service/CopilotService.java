package com.retail.copilot.service;

import com.openai.client.OpenAIClient;
import com.openai.models.chat.completions.ChatCompletionCreateParams;
import com.retail.copilot.request.CopilotRequest;
import com.retail.copilot.response.CopilotAction;
import com.retail.copilot.response.CopilotResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class CopilotService {

    private final OrderClient orderClient;
    private final OpenAIClient openAIClient;

    public CopilotResponse chat(CopilotRequest req, String bearerToken) {
        List<CopilotAction> actions = new ArrayList<>();
        String msg = req.message() != null ? req.message().toLowerCase() : "";
        Integer orderId = req.orderId();

        boolean aboutOrder   = msg.contains("order") || msg.contains("delayed") || msg.contains("shipping");
        boolean aboutPayment = msg.contains("payment") || msg.contains("charged") || msg.contains("stripe");
        boolean aboutCancel  = msg.contains("cancel");

        // Ask for orderId if talking about order-specific topics
        if ((aboutOrder || aboutPayment || aboutCancel) && orderId == null) {
            return new CopilotResponse(
                    "Sure — please provide your Order ID (e.g. 42) and I'll look it up for you.",
                    actions);
        }

        if (orderId != null) {
            try {
                Map<String, Object> order = orderClient.getOrder(orderId, bearerToken);

                String reference  = String.valueOf(order.getOrDefault("reference", "ORD-" + orderId));
                String status     = String.valueOf(order.getOrDefault("status", "UNKNOWN"));
                Object totalAmt   = order.getOrDefault("totalAmount", "0");

                // Items text
                String itemsText = "no items";
                Object itemsObj = order.get("items");
                if (itemsObj instanceof List<?> itemsList && !itemsList.isEmpty()) {
                    itemsText = itemsList.stream()
                            .filter(i -> i instanceof Map<?,?>)
                            .map(i -> {
                                Map<?,?> item = (Map<?,?>) i;
                                return item.getOrDefault("quantity", "?") + " x " + item.getOrDefault("productName", "?");
                            })
                            .collect(Collectors.joining(", "));
                }

                // Cancel action
                if (aboutCancel) {
                    if ("PENDING".equalsIgnoreCase(status)) {
                        actions.add(new CopilotAction("CANCEL_ORDER_CONFIRM", Map.of("orderId", orderId), "Cancel this order"));
                    } else {
                        actions.add(new CopilotAction("CANCEL_NOT_ALLOWED", Map.of("orderId", orderId), "Only PENDING orders can be cancelled"));
                    }
                }

                actions.add(new CopilotAction("OPEN_ORDER_DETAILS", Map.of("orderId", orderId), "View order details"));
                actions.add(new CopilotAction("CHECK_PAYMENTS",      Map.of("orderId", orderId), "Check payment status"));

                String facts = String.format(
                        "Order reference: %s. Status: %s. Total: $%s. Items: %s.",
                        reference, status, totalAmt, itemsText);

                String answer = polishWithOpenAI(req.message(), facts);
                return new CopilotResponse(answer, actions);

            } catch (Exception e) {
                log.error("Failed to fetch order {}: {}", orderId, e.getMessage());
                return new CopilotResponse("I couldn't find that order for your account.", actions);
            }
        }

        return new CopilotResponse(
                "I can help with orders and payments. Try: \"Where is my order?\" and provide your Order ID.",
                actions);
    }

    private String polishWithOpenAI(String userMessage, String facts) {
        try {
            String prompt = String.format(
                    "You are a retail support assistant. Use ONLY these facts: %s\n" +
                    "Do not invent information. Keep it to 2-4 sentences.\nUser: %s", facts, userMessage);

            var params = ChatCompletionCreateParams.builder()
                    .model("gpt-4o-mini")
                    .addSystemMessage("You are a retail support assistant. Use only provided facts. Do not invent.")
                    .addUserMessage(prompt)
                    .build();

            var response = openAIClient.chat().completions().create(params);
            return response.choices().get(0).message().content()
                    .orElse("I can see your order details, but I'm having trouble forming a response right now.");
        } catch (Exception e) {
            log.error("OpenAI call failed: {}", e.getMessage());
            return "I can see your order details. Status: " + facts.split("\\.")[1].trim();
        }
    }
}
