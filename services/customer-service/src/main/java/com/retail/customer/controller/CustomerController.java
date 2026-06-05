package com.retail.customer.controller;

import com.retail.customer.request.CustomerRequest;
import com.retail.customer.response.CustomerResponse;
import com.retail.customer.service.CustomerService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/customers")
@RequiredArgsConstructor
public class CustomerController {

    private final CustomerService customerService;

    @GetMapping("/me")
    public ResponseEntity<CustomerResponse> getProfile(Authentication auth) {
        return ResponseEntity.ok(customerService.getByEmail(auth.getName()));
    }

    @PutMapping("/me")
    public ResponseEntity<CustomerResponse> updateProfile(Authentication auth,
                                                          @RequestBody @Valid CustomerRequest request) {
        return ResponseEntity.ok(customerService.updateProfile(auth.getName(), request));
    }

    @GetMapping("/{id}")
    public ResponseEntity<CustomerResponse> getById(@PathVariable Integer id) {
        return ResponseEntity.ok(customerService.getById(id));
    }

    @GetMapping("/by-email")
    public ResponseEntity<CustomerResponse> getByEmail(@RequestParam String email) {
        return ResponseEntity.ok(customerService.getByEmail(email));
    }

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @GetMapping
    public List<CustomerResponse> getAll() {
        return customerService.getAll();
    }

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @PutMapping("/{id}")
    public ResponseEntity<CustomerResponse> update(@PathVariable Integer id,
                                                   @RequestBody @Valid CustomerRequest request) {
        return ResponseEntity.ok(customerService.update(id, request));
    }

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Integer id) {
        customerService.delete(id);
        return ResponseEntity.noContent().build();
    }
}
