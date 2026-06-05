package com.retail.product.controller;

import com.retail.product.request.InventoryRequest;
import com.retail.product.response.InventoryResponse;
import com.retail.product.service.InventoryService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/inventory")
@RequiredArgsConstructor
public class InventoryController {

    private final InventoryService inventoryService;

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @GetMapping
    public List<InventoryResponse> getAll() {
        return inventoryService.getAll();
    }

    @GetMapping("/product/{productId}")
    public ResponseEntity<InventoryResponse> getByProductId(@PathVariable Integer productId) {
        return ResponseEntity.ok(inventoryService.getByProductId(productId));
    }

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @PutMapping
    public ResponseEntity<InventoryResponse> addOrUpdate(@Valid @RequestBody InventoryRequest request) {
        return ResponseEntity.ok(inventoryService.addOrUpdate(request));
    }

    /** Called internally by order-service to decrement stock after checkout */
    @PostMapping("/product/{productId}/decrement")
    public ResponseEntity<Void> decrementStock(@PathVariable Integer productId,
                                               @RequestParam Integer qty) {
        boolean ok = inventoryService.decrementStock(productId, qty);
        return ok ? ResponseEntity.ok().build() : ResponseEntity.badRequest().build();
    }
}
