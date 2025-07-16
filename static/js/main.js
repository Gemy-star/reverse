// static/js/main.js

$(document).ready(function() {
    // This file will primarily contain general site-wide JavaScript or
    // functions that are called across multiple pages.
    // Specific page-level JS (like Swiper initialization for product detail)
    // is kept within their respective HTML templates for clarity.

    // Example: A global search function (if you add a search bar to base.html)
    // function performGlobalSearch(query) {
    //     $.ajax({
    //         url: '{% url "shop:search_products" %}', // Make sure this URL is correctly configured in Django
    //         type: 'GET',
    //         data: { q: query },
    //         dataType: 'json',
    //         success: function(response) {
    //             console.log("Search Results:", response.products);
    //             // Render search results, e.g., in a modal or on a search results page
    //         },
    //         error: function(xhr, status, error) {
    //             console.error("Search Error:", status, error);
    //         }
    //     });
    // }

    // You can add event listeners here for elements that exist on most pages,
    // like a search input in the header.
    // Example:
    // $('#search-input').on('keypress', function(e) {
    //     if (e.which == 13) { // Enter key pressed
    //         performGlobalSearch($(this).val());
    //     }
    // });
    
});
