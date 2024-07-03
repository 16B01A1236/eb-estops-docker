

const { Auth } = aws_amplify;

const awsCognitoRegion= "eu-west-1",
identityPoolId ="eu-west-1:514b95b9-74a0-4a89-8ccc-ea40408fa121",
userPoolId = "eu-west-1_t6ebYpeO2",
clientId = "2fq8dtalchrevle04i6tdkvmrd",
cognitoDomain = "quartz-eu-beta.auth.eu-west-1.amazoncognito.com",
Email = 'email',
OpenID = 'openid',
Profile = 'profile',
CognitoUser='aws.cognito.signin.user.admin';
const cognitoConfig = {
    aws_cognito_identity_pool_id: identityPoolId,
    aws_project_region: awsCognitoRegion,
    aws_cognito_region: awsCognitoRegion,
    aws_user_pools_id: userPoolId,
    aws_user_pools_web_client_id: clientId,
    federationTarget: 'COGNITO_USER_POOLS',
    oauth: {
    domain: cognitoDomain,
    redirectSignIn: 'https://estops.beta-eu.quartz.rme.amazon.dev/',
    redirectSignOut:'https://estops.beta-eu.quartz.rme.amazon.dev/logout',
    responseType: 'code',
    scope: [OpenID]
    }
};




const checkAuthentication = async () => {
    Auth.configure(cognitoConfig);
    Auth.currentAuthenticatedUser().then((user) => {
        console.log("logged in");
        
    }).
    catch((error)=>{ 
        console.log('not logged in');
        //window.location.href='https://quartz-eu-beta.auth.eu-west-1.amazoncognito.com/oauth2/authorize?client_id=2fq8dtalchrevle04i6tdkvmrd&response_type=code&scope=email+openid+phone+profile&redirect_uri=https://estops.beta-eu.quartz.rme.amazon.dev/'
    })
};

checkAuthentication();



