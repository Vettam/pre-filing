from supabase import create_async_client, AsyncClient, AsyncClientOptions
from core.config import config


class SupabaseHandler:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SupabaseHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, url: str, key: str):
        if not hasattr(self, "initialized"):
            self.url = url
            self.key = key
            self.initialized = True

    async def create_anon_client(self) -> AsyncClient:
        """
        Creates anonymous supabase client. Provides least privilage.
        Characterized by [anon] role on postgres
        """         
        return await create_async_client(
            supabase_url=self.url,
            supabase_key=self.key,
        )

    async def create_user_client(self, userSessionToken : str) -> AsyncClient:
        """
        Creates supabase client impersonating a user, by passing in
        their session token in the headers.
        """
        options = AsyncClientOptions()
        headers = options.headers
        
        # Check if `Bearer` prefix is already sent via user.
        if(userSessionToken.startswith('Bearer ')):
            headers['Authorization'] = userSessionToken
        else:
            headers['Authorization'] = f'Bearer {userSessionToken}'

        options.headers = headers

        return await create_async_client(
            supabase_url=self.url,
            supabase_key=self.key,
            options=options
        )
    
    async def create_service_client(self) -> AsyncClient:
        """
        Creates a supabase client with service role key, which
        can bypass RLS layer of DB.
        """
        return await create_async_client(
            supabase_url=self.url,
            supabase_key=config.SUPABASE_SERVICE_ROLE_KEY,
        )


handler = SupabaseHandler(url=config.SUPABASE_PROJECT_URL, key=config.SUPABASE_PROJECT_KEY)


async def get_supabase_client(userSessionToken : str = None) -> AsyncClient:
    '''
    Returns a supabase instance to communicate with the server.

    Optionally pass a user's session token to impersonate the user using this instance.
    Impersonating would result in the RLS layer of DB to trigger, hence unexpected
    data may not leak.
    '''
    if(userSessionToken == None):
        return await handler.create_anon_client()
    
    return await handler.create_user_client(userSessionToken=userSessionToken)

async def get_supabase_service_client() -> AsyncClient:
    return await handler.create_service_client()
