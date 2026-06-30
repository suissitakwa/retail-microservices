package com.retail.customer.email;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.Map;

@Service
@Slf4j
public class EmailService {

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${MAIL_PASSWORD:disabled}")
    private String resendApiKey;

    @Value("${app.mail.from:NovaMart <onboarding@resend.dev>}")
    private String fromAddress;

    @Async
    public void sendPasswordReset(String toEmail, String firstName, String resetLink) {
        send(toEmail, "Reset your NovaMart password", buildHtml(firstName, resetLink));
    }

    private void send(String toEmail, String subject, String html) {
        try {
            String body = objectMapper.writeValueAsString(Map.of(
                    "from", fromAddress,
                    "to", List.of(toEmail),
                    "subject", subject,
                    "html", html
            ));
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.resend.com/emails"))
                    .header("Authorization", "Bearer " + resendApiKey)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                log.warn("Resend API error sending to {}: {} {}", toEmail, response.statusCode(), response.body());
            } else {
                log.info("Email sent to {} via Resend (status {})", toEmail, response.statusCode());
            }
        } catch (Exception e) {
            log.warn("Failed to send email to {}: {}", toEmail, e.getMessage());
        }
    }

    private String buildHtml(String firstName, String resetLink) {
        return """
                <!DOCTYPE html>
                <html>
                <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
                  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <div style="background:#1a1a2e;padding:30px;text-align:center;">
                      <h1 style="color:#f5c518;margin:0;font-size:24px;">NovaMart</h1>
                    </div>
                    <div style="padding:30px;">
                      <h2 style="color:#333;margin-top:0;">Hi %s, reset your password</h2>
                      <p style="color:#555;">We received a request to reset your password. Click the button below — this link expires in 1 hour.</p>
                      <div style="text-align:center;margin:30px 0;">
                        <a href="%s"
                           style="background:#f5c518;color:#1a1a2e;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">
                          Reset Password
                        </a>
                      </div>
                      <p style="color:#999;font-size:13px;">If you didn't request this, you can safely ignore this email.</p>
                    </div>
                    <div style="background:#f4f4f4;padding:16px;text-align:center;">
                      <p style="color:#999;font-size:12px;margin:0;">© 2025 NovaMart</p>
                    </div>
                  </div>
                </body>
                </html>
                """.formatted(firstName, resetLink);
    }
}
