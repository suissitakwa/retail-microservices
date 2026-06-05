package com.retail.product.service;

import com.retail.product.entity.Inventory;
import com.retail.product.exception.ResourceNotFoundException;
import com.retail.product.repository.InventoryRepository;
import com.retail.product.repository.ProductRepository;
import com.retail.product.request.InventoryRequest;
import com.retail.product.response.InventoryResponse;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class InventoryService {

    private final InventoryRepository inventoryRepository;
    private final ProductRepository productRepository;

    public List<InventoryResponse> getAll() {
        return inventoryRepository.findAll().stream().map(this::toResponse).toList();
    }

    public InventoryResponse getByProductId(Integer productId) {
        return toResponse(inventoryRepository.findByProductId(productId)
                .orElseThrow(() -> new ResourceNotFoundException("Inventory not found for product: " + productId)));
    }

    @Transactional
    public InventoryResponse addOrUpdate(InventoryRequest request) {
        var product = productRepository.findById(request.productId())
                .orElseThrow(() -> new ResourceNotFoundException("Product not found: " + request.productId()));

        Inventory inv = inventoryRepository.findByProductId(request.productId())
                .orElse(new Inventory());

        inv.setProduct(product);
        inv.setQuantity(request.quantity());
        inv.setLastUpdated(LocalDateTime.now());

        return toResponse(inventoryRepository.save(inv));
    }

    @Transactional
    public boolean decrementStock(Integer productId, Integer qty) {
        int updated = inventoryRepository.decrementStock(productId, qty);
        if (updated == 0) {
            log.warn("Insufficient stock for productId={}, requested qty={}", productId, qty);
            return false;
        }
        log.info("Decremented stock: productId={}, qty={}", productId, qty);
        return true;
    }

    private InventoryResponse toResponse(Inventory i) {
        return new InventoryResponse(
                i.getId(),
                i.getProduct().getId(),
                i.getProduct().getName(),
                i.getQuantity(),
                i.getLastUpdated()
        );
    }
}
