const { createApp, ref, onMounted } = Vue;

createApp({
    setup() {
        const loading = ref(true);
        const error = ref(null);
        const status = ref(null);
        const clients = ref([]);

        // Timeline states
        const timelineType = ref('user');
        const timelineId = ref('');
        const timelineError = ref(null);
        let timelineInstance = null;

        const loadTimeline = () => {
            if (!timelineId.value) {
                timelineError.value = "Please enter an ID.";
                return;
            }

            timelineError.value = null;

            fetch(`/api/timeline/${timelineType.value}/${timelineId.value}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (!data.events || data.events.length === 0) {
                        timelineError.value = "No events found for this ID.";
                        if (timelineInstance) {
                            timelineInstance.destroy();
                            timelineInstance = null;
                        }
                        return;
                    }

                    const container = document.getElementById('timeline');

                    // Map backend events to vis-timeline format
                    const items = new vis.DataSet(data.events.map(event => ({
                        id: event.id,
                        content: event.type,
                        start: event.timestamp,
                        title: JSON.stringify(event.data, null, 2)
                    })));

                    const options = {};

                    if (timelineInstance) {
                        timelineInstance.destroy();
                    }

                    timelineInstance = new vis.Timeline(container, items, options);
                })
                .catch(err => {
                    timelineError.value = `Error fetching timeline data: ${err.message || err}`;
                });
        };

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
            clients,
            timelineType,
            timelineId,
            timelineError,
            loadTimeline
        };
    }
}).mount('#app');
