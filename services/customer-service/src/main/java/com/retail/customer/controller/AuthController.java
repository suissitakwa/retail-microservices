package com.retail.customer.controller;

import com.retail.customer.email.EmailService;
import com.retail.customer.entity.Customer;
import com.retail.customer.enums.Role;
import com.retail.customer.jwt.JwtService;
import com.retail.customer.jwt.MyUserDetails;
import com.retail.customer.repository.CustomerRepository;
import com.retail.customer.request.LoginRequest;
import com.retail.customer.request.RegisterRequest;
import com.retail.customer.response.AuthResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final CustomerRepository customerRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;
    private final EmailService emailService;

    @Value("${app.frontend.base-url:http://localhost:3000}")
    private String frontendBaseUrl;

    @PostMapping("/register")
    public ResponseEntity<AuthResponse> register(@RequestBody @Valid RegisterRequest request) {
        if (customerRepository.existsByEmail(request.email())) {
            return ResponseEntity.badRequest().build();
        }
        Customer customer = Customer.builder()
                .email(request.email())
                .password(passwordEncoder.encode(request.password()))
                .firstname(request.firstname())
                .lastname(request.lastname())
                .role(Role.ROLE_CUSTOMER)
                .address(request.address())
                .build();
        customerRepository.save(customer);
        UserDetails userDetails = new MyUserDetails(customer);
        return ResponseEntity.ok(new AuthResponse(
                jwtService.generateToken(userDetails),
                jwtService.generateRefreshToken(userDetails)
        ));
    }

    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@RequestBody @Valid LoginRequest request) {
        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password())
        );
        UserDetails userDetails = (UserDetails) auth.getPrincipal();
        return ResponseEntity.ok(new AuthResponse(
                jwtService.generateToken(userDetails),
                jwtService.generateRefreshToken(userDetails)
        ));
    }

    @PostMapping("/refresh")
    public ResponseEntity<AuthResponse> refresh(@RequestBody Map<String, String> body) {
        String refreshToken = body.get("refreshToken");
        String email = jwtService.extractEmail(refreshToken);
        Customer customer = customerRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("Customer not found"));
        UserDetails userDetails = new MyUserDetails(customer);
        if (!jwtService.isTokenValid(refreshToken, userDetails)) {
            return ResponseEntity.status(401).build();
        }
        return ResponseEntity.ok(new AuthResponse(
                jwtService.generateToken(userDetails),
                jwtService.generateRefreshToken(userDetails)
        ));
    }

    @PostMapping("/forgot-password")
    public ResponseEntity<Void> forgotPassword(@RequestBody Map<String, String> body) {
        customerRepository.findByEmail(body.get("email")).ifPresent(customer -> {
            String token = UUID.randomUUID().toString();
            customer.setResetToken(token);
            customer.setResetTokenExpiry(LocalDateTime.now().plusHours(1));
            customerRepository.save(customer);
            String resetLink = frontendBaseUrl + "/reset-password?token=" + token;
            emailService.sendPasswordReset(customer.getEmail(), customer.getFirstname(), resetLink);
        });
        return ResponseEntity.ok().build();
    }

    @PostMapping("/reset-password")
    public ResponseEntity<Void> resetPassword(@RequestBody Map<String, String> body) {
        Customer customer = customerRepository.findByResetToken(body.get("token"))
                .orElseThrow(() -> new RuntimeException("Invalid or expired reset token"));
        if (customer.getResetTokenExpiry() == null || customer.getResetTokenExpiry().isBefore(LocalDateTime.now())) {
            return ResponseEntity.badRequest().build();
        }
        customer.setPassword(passwordEncoder.encode(body.get("newPassword")));
        customer.setResetToken(null);
        customer.setResetTokenExpiry(null);
        customerRepository.save(customer);
        return ResponseEntity.ok().build();
    }
}
