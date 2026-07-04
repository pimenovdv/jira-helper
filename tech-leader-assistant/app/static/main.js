const { createApp, ref, onMounted } = Vue;

createApp({
    setup() {
        const loading = ref(true);
        const error = ref(null);
        const status = ref(null);
        const clients = ref([]);

        // Tasks Dashboard states
        const tasks = ref([]);
        const tasksLoading = ref(false);
        const tasksError = ref(null);



        // Releases Dashboard states
        const releases = ref([]);
        const releasesLoading = ref(false);
        const releasesError = ref(null);

        const loadReleases = () => {
            releasesLoading.value = true;
            releasesError.value = null;

            fetch('/api/dashboard/releases')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    releases.value = data.releases || [];
                    releasesLoading.value = false;
                })
                .catch(err => {
                    releasesError.value = `Error fetching releases: ${err.message || err}`;
                    releasesLoading.value = false;
                });
        };

        // Chat states
        const chatMessages = ref([]);
        const chatInput = ref('');
        const chatLoading = ref(false);
        const chatError = ref(null);

        const sendChat = () => {
            if (!chatInput.value.trim() || chatLoading.value) return;

            const query = chatInput.value.trim();
            chatMessages.value.push({ role: 'user', content: query });
            chatInput.value = '';
            chatLoading.value = true;
            chatError.value = null;

            // Scroll to bottom
            setTimeout(() => {
                const el = document.getElementById('chat-messages');
                if (el) el.scrollTop = el.scrollHeight;
            }, 50);

            fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: query })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                chatMessages.value.push({
                    role: 'assistant',
                    content: data.answer,
                    documents: data.documents
                });
                chatLoading.value = false;

                // Scroll to bottom
                setTimeout(() => {
                    const el = document.getElementById('chat-messages');
                    if (el) el.scrollTop = el.scrollHeight;
                }, 50);
            })
            .catch(err => {
                chatError.value = `Error communicating with chat API: ${err.message || err}`;
                chatLoading.value = false;
            });
        };

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

        const loadTasks = () => {
            tasksLoading.value = true;
            tasksError.value = null;

            fetch('/api/dashboard/tasks')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    tasks.value = data.tasks || [];
                    tasksLoading.value = false;
                })
                .catch(err => {
                    tasksError.value = `Error fetching tasks: ${err.message || err}`;
                    tasksLoading.value = false;
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
            tasks,
            tasksLoading,
            tasksError,
            loadTasks,
            releases,
            releasesLoading,
            releasesError,
            loadReleases,
            loadTimeline,
            chatMessages,
            chatInput,
            chatLoading,
            chatError,
            sendChat
        };
    }
}).mount('#app');
