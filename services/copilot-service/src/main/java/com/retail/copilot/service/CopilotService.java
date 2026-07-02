package com.retail.copilot.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.openai.client.OpenAIClient;
import com.openai.core.JsonValue;
import com.openai.models.FunctionDefinition;
import com.openai.models.FunctionParameters;
import com.openai.models.chat.completions.ChatCompletionCreateParams;
import com.openai.models.chat.completions.ChatCompletionToolMessageParam;
import com.retail.copilot.request.CopilotRequest;
import com.retail.copilot.response.CopilotAction;
import com.retail.copilot.response.CopilotResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class CopilotService {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final String MODEL = "gpt-4o-mini";

    private final OrderClient orderClient;
    private final OpenAIClient openAIClient;

    private static final FunctionParameters ORDER_ID_PARAMS = FunctionParameters.builder()
            .putAdditionalProperty("type", JsonValue.from("object"))
            .putAdditionalProperty("properties", JsonValue.from(Map.of(
                    "orderId", Map.of("type", "integer", "description", "The numeric order ID"))))
            .putAdditionalProperty("required", JsonValue.from(List.of("orderId")))
            .build();

    private static final FunctionParameters NO_PARAMS = FunctionParameters.builder()
            .putAdditionalProperty("type", JsonValue.from("object"))
            .putAdditionalProperty("properties", JsonValue.from(Map.of()))
            .putAdditionalProperty("required", JsonValue.from(List.of()))
            .build();

    private static final FunctionParameters LIMIT_PARAMS = FunctionParameters.builder()
            .putAdditionalProperty("type", JsonValue.from("object"))
            .putAdditionalProperty("properties", JsonValue.from(Map.of(
                    "limit", Map.of("type", "integer", "description", "Number of recent orders to fetch (default 5, max 10)"))))
            .putAdditionalProperty("required", JsonValue.from(List.of()))
            .build();

    public CopilotResponse chat(CopilotRequest req, String bearerToken) {
        List<CopilotAction> actions = new ArrayList<>();
        String userMessage = req.message() != null ? req.message() : "";
        String context = req.orderId() != null
                ? "The user is referring to order ID " + req.orderId() + ". " + userMessage
                : userMessage;

        try {
            var params = ChatCompletionCreateParams.builder()
                    .model(MODEL)
                    .addSystemMessage("""
                            You are a retail support assistant for NovaMart. Rules:
                            1. If the user asks about their latest/recent orders or purchases WITHOUT a specific order ID, call fetch_recent_orders first.
                            2. If the user provides or mentions a specific order ID, call fetch_order with that ID.
                            3. If the user asks about spending or total amount spent, call fetch_spending_summary.
                            4. Call cancel_order only if the user explicitly asks to cancel a specific order.
                            5. Call open_order_details or check_payment_status to suggest navigation for a specific order.
                            6. Never invent order data — only use what the tools return.
                            7. Keep responses friendly and concise (2-4 sentences).
                            8. If no orders exist, tell the user they have no orders yet.
                            """)
                    .addUserMessage(context)
                    .addFunctionTool(FunctionDefinition.builder()
                            .name("fetch_recent_orders")
                            .description("Fetch the customer's most recent orders. Use this when the user asks about their latest order, recent purchases, or order history without specifying an order ID.")
                            .parameters(LIMIT_PARAMS)
                            .build())
                    .addFunctionTool(FunctionDefinition.builder()
                            .name("fetch_spending_summary")
                            .description("Calculate how much the customer has spent in total. Use this when the user asks about spending, total spent, or money questions.")
                            .parameters(NO_PARAMS)
                            .build())
                    .addFunctionTool(FunctionDefinition.builder()
                            .name("fetch_order")
                            .description("Retrieve details of a specific order by ID. Call this only when a specific order ID is known.")
                            .parameters(ORDER_ID_PARAMS)
                            .build())
                    .addFunctionTool(FunctionDefinition.builder()
                            .name("cancel_order")
                            .description("Request cancellation of an order. Only call if the user explicitly wants to cancel.")
                            .parameters(ORDER_ID_PARAMS)
                            .build())
                    .addFunctionTool(FunctionDefinition.builder()
                            .name("open_order_details")
                            .description("Suggest navigating to the order details page.")
                            .parameters(ORDER_ID_PARAMS)
                            .build())
                    .addFunctionTool(FunctionDefinition.builder()
                            .name("check_payment_status")
                            .description("Suggest checking the payment status for an order.")
                            .parameters(ORDER_ID_PARAMS)
                            .build())
                    .build();

            var response = openAIClient.chat().completions().create(params);
            var message = response.choices().get(0).message();
            var toolCalls = message.toolCalls().orElse(List.of());

            if (toolCalls.isEmpty()) {
                return new CopilotResponse(message.content().orElse("I'm here to help with your orders."), actions);
            }

            var followUp = ChatCompletionCreateParams.builder()
                    .model(MODEL)
                    .addSystemMessage("You are a retail support assistant. Answer in 2-4 sentences using only the provided tool results.")
                    .addUserMessage(context)
                    .addMessage(message);

            for (var toolCall : toolCalls) {
                if (!toolCall.isFunction()) continue;
                var fn = toolCall.asFunction();
                String toolResult = dispatch(fn.function().name(), fn.function().arguments(), bearerToken, actions);
                followUp.addMessage(ChatCompletionToolMessageParam.builder()
                        .toolCallId(fn.id())
                        .content(toolResult)
                        .build());
            }

            var finalResponse = openAIClient.chat().completions().create(followUp.build());
            String answer = finalResponse.choices().get(0).message().content()
                    .orElse("I've looked into your order. Please see the details below.");
            return new CopilotResponse(answer, actions);

        } catch (Exception e) {
            log.warn("Copilot chat failed: {}", e.getMessage());
            return new CopilotResponse(
                    "The AI assistant is temporarily unavailable. You can still view your orders in the Orders section.",
                    List.of());
        }
    }

    private String dispatch(String toolName, String argsJson, String bearerToken, List<CopilotAction> actions) {
        Integer orderId = extractOrderId(argsJson);
        return switch (toolName) {
            case "fetch_recent_orders" -> fetchRecentOrders(argsJson, bearerToken, actions);
            case "fetch_spending_summary" -> fetchSpendingSummary(bearerToken);
            case "fetch_order" -> fetchOrderFacts(orderId, bearerToken);
            case "cancel_order" -> handleCancel(orderId, bearerToken, actions);
            case "open_order_details" -> {
                if (orderId != null)
                    actions.add(new CopilotAction("OPEN_ORDER_DETAILS", Map.of("orderId", orderId), "View order details"));
                yield "Navigation action queued.";
            }
            case "check_payment_status" -> {
                if (orderId != null)
                    actions.add(new CopilotAction("CHECK_PAYMENTS", Map.of("orderId", orderId), "Check payment status"));
                yield "Navigation action queued.";
            }
            default -> "Unknown tool.";
        };
    }

    private Integer extractOrderId(String argsJson) {
        try {
            var node = MAPPER.readTree(argsJson);
            return node.has("orderId") ? node.get("orderId").asInt() : null;
        } catch (Exception e) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private String fetchRecentOrders(String argsJson, String bearerToken, List<CopilotAction> actions) {
        int limit = 5;
        try {
            var node = MAPPER.readTree(argsJson);
            if (node.has("limit")) limit = Math.min(node.get("limit").asInt(), 10);
        } catch (Exception ignored) {}

        try {
            Map<String, Object> page = orderClient.getMyOrders(limit, bearerToken);
            List<Map<String, Object>> orders = (List<Map<String, Object>>) page.getOrDefault("content", List.of());
            if (orders.isEmpty()) return "The customer has no orders.";

            actions.add(new CopilotAction("OPEN_ORDERS", Map.of(), "View all orders"));

            StringBuilder sb = new StringBuilder();
            for (Map<String, Object> o : orders) {
                sb.append(String.format("Order #%s (%s) — %s — $%s%n",
                        o.get("id"), o.get("reference"), o.get("status"), o.get("totalAmount")));
            }
            return sb.toString();
        } catch (Exception e) {
            log.warn("Failed to fetch recent orders: {}", e.getMessage());
            return "Could not retrieve orders.";
        }
    }

    @SuppressWarnings("unchecked")
    private String fetchSpendingSummary(String bearerToken) {
        try {
            Map<String, Object> page = orderClient.getMyOrders(100, bearerToken);
            List<Map<String, Object>> orders = (List<Map<String, Object>>) page.getOrDefault("content", List.of());
            if (orders.isEmpty()) return "The customer has no orders and has spent $0.00.";

            BigDecimal total = BigDecimal.ZERO;
            for (Map<String, Object> o : orders) {
                Object amt = o.get("totalAmount");
                if (amt != null) total = total.add(new BigDecimal(amt.toString()));
            }
            return String.format("Total spent across all %d orders: $%s.", orders.size(), total);
        } catch (Exception e) {
            log.warn("Failed to fetch spending summary: {}", e.getMessage());
            return "Could not retrieve spending data.";
        }
    }

    private String fetchOrderFacts(Integer orderId, String bearerToken) {
        if (orderId == null) return "No order ID was provided.";
        try {
            Map<String, Object> order = orderClient.getOrder(orderId, bearerToken);
            return String.format("Reference: %s. Status: %s. Total: $%s. Items: %s.",
                    order.get("reference"), order.get("status"), order.get("totalAmount"), itemsText(order));
        } catch (Exception e) {
            log.warn("Failed to fetch order {}: {}", orderId, e.getMessage());
            return "Order not found or you don't have access to it.";
        }
    }

    private String handleCancel(Integer orderId, String bearerToken, List<CopilotAction> actions) {
        if (orderId == null) return "No order ID was provided.";
        try {
            Map<String, Object> order = orderClient.getOrder(orderId, bearerToken);
            String status = String.valueOf(order.get("status"));
            if ("PENDING".equalsIgnoreCase(status)) {
                actions.add(new CopilotAction("CANCEL_ORDER_CONFIRM", Map.of("orderId", orderId), "Cancel this order"));
                return "Order " + orderId + " is PENDING and eligible for cancellation.";
            } else {
                actions.add(new CopilotAction("CANCEL_NOT_ALLOWED", Map.of("orderId", orderId), "Only PENDING orders can be cancelled"));
                return "Order " + orderId + " has status " + status + " and cannot be cancelled.";
            }
        } catch (Exception e) {
            log.warn("Failed to fetch order {} for cancel check: {}", orderId, e.getMessage());
            return "Order not found.";
        }
    }

    @SuppressWarnings("unchecked")
    private String itemsText(Map<String, Object> order) {
        Object itemsObj = order.get("items");
        if (!(itemsObj instanceof List<?> itemsList) || itemsList.isEmpty()) return "no items";

        StringBuilder sb = new StringBuilder();
        for (Object item : itemsList) {
            if (!(item instanceof Map<?, ?> itemMap)) continue;
            if (sb.length() > 0) sb.append(", ");
            sb.append(itemMap.get("quantity")).append(" x ").append(itemMap.get("productName"));
        }
        return sb.length() == 0 ? "no items" : sb.toString();
    }
}
