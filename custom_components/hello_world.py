# The domain of your component. Equal to the filename of your component.
DOMAIN = "hello_world"


def setup(hass, config):
    """Setup the hello_world component."""
    # States are in the format DOMAIN.OBJECT_ID.
    hass.states.set('hello_world.Hello_World', 'Works!',{"foo":"bar"})

    # Return boolean to indicate that initialization was successfully.
    return True
