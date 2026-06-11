package com.retail.product;

import com.retail.product.entity.Category;
import com.retail.product.entity.Inventory;
import com.retail.product.entity.Product;
import com.retail.product.exception.ResourceNotFoundException;
import com.retail.product.repository.CategoryRepository;
import com.retail.product.repository.ProductRepository;
import com.retail.product.request.ProductRequest;
import com.retail.product.response.ProductResponse;
import com.retail.product.service.ProductService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ProductServiceTest {

    @Mock ProductRepository productRepository;
    @Mock CategoryRepository categoryRepository;

    ProductService service;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new ProductService(productRepository, categoryRepository);
    }

    // ── helpers ───────────────────────────────────────────────────────────────

    private Category category(Integer id, String name) {
        Category c = new Category();
        c.setId(id);
        c.setName(name);
        return c;
    }

    private Product product(Integer id, String name, BigDecimal price, Category cat) {
        Inventory inv = new Inventory();
        inv.setQuantity(50);

        Product p = Product.builder()
                .id(id).name(name).description("desc")
                .imageUrl("http://img.test").price(price)
                .category(cat).inventory(inv).build();
        inv.setProduct(p);
        return p;
    }

    // ── getAll ────────────────────────────────────────────────────────────────

    @Test
    void getAll_returnsMappedResponses() {
        Category cat = category(1, "Electronics");
        when(productRepository.findAll()).thenReturn(List.of(
                product(1, "Headphones", new BigDecimal("99.99"), cat),
                product(2, "Keyboard",   new BigDecimal("49.99"), cat)
        ));

        List<ProductResponse> result = service.getAll();

        assertThat(result).hasSize(2);
        assertThat(result.get(0).name()).isEqualTo("Headphones");
        assertThat(result.get(0).stockQuantity()).isEqualTo(50);
        assertThat(result.get(0).category().name()).isEqualTo("Electronics");
        assertThat(result.get(1).name()).isEqualTo("Keyboard");
    }

    @Test
    void getAll_returnsEmptyList_whenNoProducts() {
        when(productRepository.findAll()).thenReturn(List.of());
        assertThat(service.getAll()).isEmpty();
    }

    // ── getById ───────────────────────────────────────────────────────────────

    @Test
    void getById_returnsProduct_whenFound() {
        Category cat = category(1, "Gaming");
        when(productRepository.findById(1)).thenReturn(Optional.of(
                product(1, "Mouse", new BigDecimal("29.99"), cat)
        ));

        ProductResponse result = service.getById(1);

        assertThat(result.id()).isEqualTo(1);
        assertThat(result.name()).isEqualTo("Mouse");
        assertThat(result.price()).isEqualByComparingTo("29.99");
    }

    @Test
    void getById_throwsNotFound_whenMissing() {
        when(productRepository.findById(99)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getById(99))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Product not found: 99");
    }

    // ── getByCategory ─────────────────────────────────────────────────────────

    @Test
    void getByCategory_returnsProductsInCategory() {
        Category cat = category(2, "Fashion");
        when(productRepository.findByCategoryId(2)).thenReturn(List.of(
                product(10, "T-Shirt", new BigDecimal("19.99"), cat)
        ));

        List<ProductResponse> result = service.getByCategory(2);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).name()).isEqualTo("T-Shirt");
        assertThat(result.get(0).category().id()).isEqualTo(2);
    }

    // ── create ────────────────────────────────────────────────────────────────

    @Test
    void create_savesProductWithDefaultStock50() {
        Category cat = category(1, "Electronics");
        when(categoryRepository.findById(1)).thenReturn(Optional.of(cat));

        Product saved = product(5, "Speaker", new BigDecimal("79.99"), cat);
        when(productRepository.save(any(Product.class))).thenReturn(saved);

        ProductRequest req = new ProductRequest("Speaker", "Bluetooth speaker",
                "http://img.test", new BigDecimal("79.99"), 1);

        ProductResponse result = service.create(req);

        assertThat(result.name()).isEqualTo("Speaker");
        assertThat(result.stockQuantity()).isEqualTo(50);
        verify(productRepository).save(any(Product.class));
    }

    @Test
    void create_throwsNotFound_whenCategoryMissing() {
        when(categoryRepository.findById(99)).thenReturn(Optional.empty());

        ProductRequest req = new ProductRequest("Test", "desc", null,
                new BigDecimal("10.00"), 99);

        assertThatThrownBy(() -> service.create(req))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("Category not found: 99");
    }

    // ── delete ────────────────────────────────────────────────────────────────

    @Test
    void delete_callsRepository() {
        service.delete(3);
        verify(productRepository).deleteById(3);
    }

    // ── toResponse — null safety ───────────────────────────────────────────────

    @Test
    void toResponse_handlesNullInventoryAndCategory() {
        Product p = Product.builder()
                .id(1).name("Bare product").price(new BigDecimal("5.00"))
                .category(null).inventory(null).build();

        ProductResponse response = service.toResponse(p);

        assertThat(response.stockQuantity()).isNull();
        assertThat(response.category()).isNull();
    }
}
