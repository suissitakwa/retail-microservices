package com.retail.product;

import com.retail.product.entity.Inventory;
import com.retail.product.entity.Product;
import com.retail.product.exception.ResourceNotFoundException;
import com.retail.product.repository.InventoryRepository;
import com.retail.product.repository.ProductRepository;
import com.retail.product.request.InventoryRequest;
import com.retail.product.response.InventoryResponse;
import com.retail.product.service.InventoryService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.math.BigDecimal;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

class InventoryServiceTest {

    @Mock InventoryRepository inventoryRepository;
    @Mock ProductRepository productRepository;

    InventoryService service;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new InventoryService(inventoryRepository, productRepository);
    }

    // ── helpers ───────────────────────────────────────────────────────────────

    private Product product(Integer id, String name) {
        return Product.builder().id(id).name(name)
                .price(new BigDecimal("10.00")).build();
    }

    private Inventory inventory(Integer id, Product product, Integer qty) {
        Inventory inv = new Inventory();
        inv.setId(id);
        inv.setProduct(product);
        inv.setQuantity(qty);
        return inv;
    }

    // ── getByProductId ────────────────────────────────────────────────────────

    @Test
    void getByProductId_returnsInventory_whenFound() {
        Product p = product(1, "Headphones");
        when(inventoryRepository.findByProductId(1))
                .thenReturn(Optional.of(inventory(10, p, 35)));

        InventoryResponse result = service.getByProductId(1);

        assertThat(result.productId()).isEqualTo(1);
        assertThat(result.productName()).isEqualTo("Headphones");
        assertThat(result.quantity()).isEqualTo(35);
    }

    @Test
    void getByProductId_throwsNotFound_whenMissing() {
        when(inventoryRepository.findByProductId(99)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getByProductId(99))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Inventory not found for product: 99");
    }

    // ── addOrUpdate ───────────────────────────────────────────────────────────

    @Test
    void addOrUpdate_updatesExistingInventory() {
        Product p = product(1, "Keyboard");
        Inventory existing = inventory(5, p, 20);
        when(productRepository.findById(1)).thenReturn(Optional.of(p));
        when(inventoryRepository.findByProductId(1)).thenReturn(Optional.of(existing));
        when(inventoryRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        InventoryResponse result = service.addOrUpdate(new InventoryRequest(1, 100));

        assertThat(result.quantity()).isEqualTo(100);
        assertThat(result.productName()).isEqualTo("Keyboard");
    }

    @Test
    void addOrUpdate_createsNewInventory_whenNoneExists() {
        Product p = product(2, "Mouse");
        when(productRepository.findById(2)).thenReturn(Optional.of(p));
        when(inventoryRepository.findByProductId(2)).thenReturn(Optional.empty());
        when(inventoryRepository.save(any())).thenAnswer(i -> {
            Inventory inv = i.getArgument(0);
            inv.setId(99);
            return inv;
        });

        InventoryResponse result = service.addOrUpdate(new InventoryRequest(2, 75));

        assertThat(result.quantity()).isEqualTo(75);
    }

    @Test
    void addOrUpdate_throwsNotFound_whenProductMissing() {
        when(productRepository.findById(99)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.addOrUpdate(new InventoryRequest(99, 10)))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Product not found: 99");
    }

    // ── decrementStock ────────────────────────────────────────────────────────

    @Test
    void decrementStock_returnsTrue_whenStockSufficient() {
        when(inventoryRepository.decrementStock(1, 5)).thenReturn(1);
        assertThat(service.decrementStock(1, 5)).isTrue();
    }

    @Test
    void decrementStock_returnsFalse_whenInsufficientStock() {
        when(inventoryRepository.decrementStock(1, 100)).thenReturn(0);
        assertThat(service.decrementStock(1, 100)).isFalse();
    }
}
