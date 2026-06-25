const { createApp, ref, onMounted } = Vue;

createApp({
    setup() {
        const loading = ref(true);
        const error = ref(null);
        const status = ref(null);
        const clients = ref([]);

        onMounted(() => {
            fetch('/api/health')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    status.value = data.status;
                    clients.value = data.clients || [];
                    loading.value = false;
                })
                .catch(err => {
                    error.value = `Error fetching health data: ${err.message || err}`;
                    loading.value = false;
                });
        });

        return {
            loading,
            error,
            status,
            clients
        };
    }
}).mount('#app');
